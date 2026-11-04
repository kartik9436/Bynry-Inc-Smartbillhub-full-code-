# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30:
#           *"Im okay with this"*.   Screens: the Print bills screen
#           ⚠ AMENDED 2026-09-01 — CR-053 task 14's named format parameter:
#           `format` on the body or the query string, refused BY NAME when
#           nobody has registered it. OQ-1167 stays OPEN.
# Rules:    BR-NOT-1030 (an unregistered print file format is refused by name
#           and never substituted) · BR-NOT-029 (the PDF set plus the manifest, and its fourteen
#           columns) · BR-CUS-674 (an address is READ here and never written) ·
#           BR-BIL-051 (a batch does not hold the browser) · BR-SHL-025 /
#           BR-IDN-009 (server-enforced RBAC) · BR-SHL-020 (a refusal a human
#           can act on) · BR-TEN-043 / G6 (event time is an ARGUMENT) ·
#           B12 r1 §3 (202 + job_id for every async op) · CLAUDE.md rule 1
# Defects:  DEF-2487 (never queue into a void) · DEF-2734 (a lazily-built
#           download arrives empty — why neither route below streams)
# Tests:    06-backend/tests/test_cr053_print_set.py
# Impacts:  config/urls.py (the include) · apps/billing/print_set.py (the work)
#           · 07-frontend PrintBillsPage
# ───────────────────────────────────────────────────────
"""`GET`/`POST /billing/print-sets` — hand one cycle's bills to a printer.

WHY THIS FILE IS NOT `apps/billing/api.py`. That module is the busiest file in
billing and three lanes have been in it this week; `documents_api.py`,
`corrections_api.py`, `budget_api.py` and `templates_api.py` are each a separate
`urlpatterns` included from `config/urls.py` for exactly that reason. This is the
fifth, and it follows their shape hop for hop.

THE NAMED FORMAT PARAMETER (CR-053 TASK 14) — AND WHAT IT DOES NOT SETTLE
════════════════════════════════════════════════════════════════════════════
`format` names which file shape the vendor's list is written in. It is REFUSED
by name when nobody has registered it, and the refusal prints the names that
exist — never a quiet fallback to the default, because a print vendor handed a
shape their loader does not read either stops or reads the wrong field into the
wrong place, and the second one is bills posted to the wrong people.

**`OQ-1167` IS STILL OPEN AND THIS ROUTE DOES NOT CLOSE IT.** One format is
registered: `BR-NOT-029`'s own fourteen columns, one row per bill, as the CSV
this product already hands over. Which format a particular vendor wants, which
fields in which order, and how a period's bills are delimited are facts only
they hold. `GET` publishes the list so a screen can offer the choice the day
there is one to make; there is no picker today because a control with a single
option is content a clerk reads for no decision (B14 rule 32).

TWO VERBS, AND THE GET IS THE HALF THAT MAKES THE SCREEN HONEST
════════════════════════════════════════════════════════════════════════════
**`GET`** answers *what would this print set contain?* — how many bills the
filters select, the ceiling in force, whether a worker would run it, and the
measured time. It writes nothing and starts nothing, so a clerk can look before
committing a worker to eight minutes. Without it the screen would have to say
*"press the button and find out"*, which is how a person ends up running a
25,000-bill set to discover it is refused.

**`POST`** produces the set. With `background: true` it enqueues on billing's
own queue and answers **202** with the poll address; with nothing that would run
the job it runs INLINE and answers **201** saying so on `background: false`
(`DEF-2487`, hard-won law 3 — an accepted job nothing will execute is strictly
worse than the visible failure it replaced). The same fallback
`api.run_findings` takes, and the caller can tell which happened from the status
code without parsing prose.

THE DOWNLOAD IS NOT HERE, AND THAT IS THE POINT (DEF-2734)
════════════════════════════════════════════════════════════════════════════
The finished archive is served by the PLATFORM route
`GET /api/exports/{job_id}/file`, which hands over a file that already exists —
since 2026-10-02 a 4-hour signed link to the S3 object at
`t/<web name>/export/…` (PO: exports move to S3, `DEF-MET-4954`) — and evaluates
no lazy body. `print_set.register()` declares the job kind downloadable there.

Mounting a download of our own would have meant building the archive inside a
response, and `DEF-2734` is what that costs: two CSV routes streamed a lazy
generator, the tenant context was cleared when the view returned, and the file
arrived as a header with no rows — *the download succeeded and nothing errored*.
There is no lazy body anywhere in this feature; the archive is complete on disk
before any byte of it is served.

RBAC, AND WHY IT IS NOT `AnyTenantRole`
════════════════════════════════════════════════════════════════════════════
Producing a print set is the act that puts a customer's name and home address
into a file somebody carries to a mail house. `AdminOrClerk` on both verbs —
including the GET, which counts a population and states a ceiling and nothing
else, but does so over the same selection. `BR-SHL-025` is server-enforced here;
the screen's disabled control is a courtesy that saves a round trip and is never
the guard.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import print_formats, print_set, selectors
from apps.billing.exceptions import BillingRuleError
from core import errors, jobs as core_jobs
from core.pagination import StandardPagination
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

#: What this feature cannot do, on every response, so no screen has to guess and
#: no reader has to take an absence on trust (the `unavailable` channel
#: `apps/billing/api.py` and `documents.py` both use).
#:
#: ⚠ **THE SECOND ENTRY IS `BR-NOT-029` CLAUSE (c) SAID OUT LOUD.** A vendor who
#: assumes we CASS-certified or barcoded a file mails it at the wrong rate or
#: not at all, and a product that stays quiet about a standard it does not
#: perform is hard-won law 1 with a stamp on it.
PRINT_SET_UNAVAILABLE: tuple[dict[str, str], ...] = (
    {
        "code": "only_one_print_file_format_exists",
        # OQ-1167 · CR-053 task 14 — the id stays in this comment, never in
        # the sentence: G28 keeps a register id off a utility user's screen.
        # ⚠ THE SENTENCE CHANGED ON 2026-09-01 AND THE ABSENCE DID NOT GO AWAY.
        # It used to say we had guessed at no machine-readable file at all;
        # there is now a named-format registry with ONE format in it, which is
        # the list this product already hands over. What is still missing is a
        # PARTICULAR vendor's shape, and that is still theirs to state.
        "detail": "this produces the printable pages and one list that goes with them, "
        "in the only file shape this system knows: a comma-separated list with the "
        "column names on the first line. A larger printer usually wants its own file "
        "shape — different columns, different order, sometimes fixed-width text — and "
        "that is theirs to specify. Tell us what yours looks like and we will add it; "
        "we will not guess at it.",
    },
    {
        "code": "no_mail_standards_are_performed_here",
        # BR-NOT-029 clause (c). The three standard names are the vendor's own
        # vocabulary and belong in front of a person; the rule id does not.
        "detail": "the addresses in this file are our own records, exactly as the account "
        "holder gave them. They have not been CASS-certified, they have not been "
        "NCOA-processed, and no Intelligent Mail barcode has been applied. Your mail house "
        "does all three; we do none of them and do not claim to.",
    },
    {
        "code": "address_line_2_and_country_have_no_column",
        # DEF-2847 — the schema gap. Named in the comment, not in the sentence.
        "detail": "the list carries both columns because that is the agreed shape, and both "
        "are always empty: we have nowhere to record a second address line or a country. "
        "Neither is filled in by us and neither is cut out of the first line, because a "
        "guessed address is mail delivered to the wrong house.",
    },
    {
        "code": "nothing_is_delivered",
        # BR-NOT-013 — delivery is out of this release.
        "detail": "the set is produced and handed to you. Nothing is posted, emailed or sent "
        "anywhere by this product; it ends with the pages and the paperwork that goes with "
        "them.",
    },
)


def _refusal(broken: BillingRuleError) -> errors.BizError:
    """The service's own sentence, as the one catalog exception G9 allows.

    The sentence travels in `params.detail` because it is written for a clerk
    (BR-SHL-020): *"this print set covers 41,000 bills and this deployment
    accepts 25,000 at a time"* is something a person can act on, and
    `BIZ-CAP` on its own is not. Identical in shape to
    `documents_api._refusal`.
    """
    return errors.BizError(
        errors.BIZ_CAP,
        br_ref=getattr(broken, "br_ref", None) or "BR-NOT-029",
        message_key="billing.printSet.refused",
        params={"detail": str(broken)},
    )


def _filters_from(request: Any, payload: dict[str, Any]) -> dict[str, str]:
    """The caller's selection, in the S30 list's OWN filter grammar.

    Accepted from `f.<name>` query params AND from a `filters` object on the
    body, so a screen can post the very query string it is displaying — the
    same posture `tenancy.api.list_export` takes, and for the same reason: a
    print set must cover exactly what the bills list showed, never an
    approximation of it. Anything outside `selectors.INVOICE_FILTERS` is
    IGNORED rather than refused (BR-SHL-011).

    `status` is dropped here as well as in the selection: `print_set
    .print_set_selection` decides it, and a filter the server is going to
    override should not be echoed back as though it had been honoured.
    """
    chosen: dict[str, str] = {}
    for name in selectors.INVOICE_FILTERS:
        if name == "status":
            continue
        raw = request.query_params.get(f"f.{name}")
        if raw:
            chosen[name] = str(raw)
    body = payload.get("filters")
    if isinstance(body, dict):
        for name, value in body.items():
            if name in selectors.INVOICE_FILTERS and name != "status" and value not in (None, ""):
                chosen[str(name)] = str(value)
    return chosen


def _format_from(request: Any, payload: dict[str, Any]) -> str | None:
    """The caller's chosen file shape — body first, then `?format=`, else None.

    ⚠ **AN UNKNOWN NAME IS NOT DROPPED HERE, WHICH IS THE OPPOSITE OF WHAT
    `_filters_from` DOES ABOVE, AND THE DIFFERENCE IS DELIBERATE.** An
    unrecognised FILTER is ignored (`BR-SHL-011`) because the worst it can do is
    widen a selection a clerk is looking at. An unrecognised FORMAT is refused
    by `print_formats.get`, because the worst IT can do is hand a print vendor a
    file their loader misreads — and a misread field is a bill posted to the
    wrong person. Ignoring it would be a silent fallback to the default, which
    is the one behaviour `BR-NOT-1030` forbids.

    `None` means *nothing was asked for*, which is not the same as a bad name:
    it gets the registry's default, exactly as every caller did before this
    parameter existed.
    """
    body = payload.get("format")
    if isinstance(body, str) and body.strip():
        return body
    query = request.query_params.get("format")
    return query if query else None


def _payload_of(request: Any) -> dict[str, Any]:
    data = getattr(request, "data", None)
    return data if isinstance(data, dict) else {}


def _wants_background(payload: dict[str, Any]) -> bool:
    """Did the caller ask for a worker? LITERAL `true` and nothing else.

    `"yes"`, `1` and a missing key all mean *no* — the same posture
    `api._wants_background` takes.

    ⚠ **IT NO LONGER DECIDES WHERE THE SET IS BUILT (DEF-BIL-9152, 2.455.1).**
    A worker consuming billing's queue is always handed the set; this flag only
    decides whether falling back to inline is logged as a broken promise.
    """
    return payload.get("background") is True


def _preview(filters: dict[str, str]) -> dict[str, Any]:
    """What a set over these filters WOULD be. Counts; never renders.

    One `COUNT(*)` over the selection the bills list already knows how to build.
    The estimate is `print_set.MEASURED_SECONDS_PER_BILL`, which is a
    MEASUREMENT and not a budget — it is here so the screen can say *"about four
    minutes"* rather than *"this may take a while"*.
    """
    forecast = print_set.forecast_print_set(filters)
    count = forecast.bills
    ready, reason = print_set.would_run()
    ceiling = print_set.max_bills_per_print_set()
    return {
        "bill_count": count,
        # ── SCREEN 28's FOUR TILES (`DEF-BIL-5354`) ────────────────────────
        # *"404 will print · 8 held back, each with a reason · ~2,424 pages ·
        # 412 in this period"*, and the blueprint's own clause about them is
        # arithmetic: *"404 + 8 = 412. A set that printed 404 of 412 without
        # saying so sends a print shop a short run and tells nobody."* All four
        # come off ONE forecast so they cannot disagree with each other.
        #
        # Before this, a clerk learned what was held only from `held-back.csv`
        # INSIDE the finished archive — several minutes of a worker's time
        # after the question was asked.
        "will_print": forecast.will_print,
        "held_back": forecast.held,
        # Non-zero reasons only, in the order a bill is judged in. The CODE
        # travels and the WORDS are the screen's: B14 rule 32 keeps an internal
        # code off a clerk's screen, and the eleven catalogues are where a
        # sentence belongs (rule 35).
        "held_reasons": [{"code": code, "bills": bills} for code, bills in forecast.held_by_reason],
        # FALSE means the address question could not be asked at all, which is
        # NOT *"nothing is held"*. The screen states it rather than printing a
        # confident zero (BR-SHL-020, hard-won law 2's mirror).
        "held_reasons_complete": forecast.addresses_readable,
        "pages": forecast.pages,
        "pages_per_bill": print_set.MEASURED_PAGES_PER_BILL,
        "printable_statuses": list(print_set.PRINTABLE_STATUSES),
        "max_bills": ceiling,
        "over_ceiling": bool(ceiling and count > ceiling),
        "estimated_seconds": round(count * print_set.MEASURED_SECONDS_PER_BILL, 1),
        "manifest_columns": list(print_set.MANIFEST_HEADER),
        # CR-053 task 14 — WHICH FILE SHAPES EXIST, so a screen can one day
        # offer the choice without a server change. There is one today and no
        # screen draws a picker for it: a control with a single option is
        # content a clerk reads for no decision (B14 rule 32). The refusal a
        # wrong name earns prints the same list, so a caller is never left
        # guessing the right word.
        "formats": print_formats.describe_all(),
        "format": print_formats.DEFAULT_FORMAT_NAME,
        # `reason` is a short technical phrase for the log and NEVER a sentence
        # for a screen (CR-016: no internal references in front of a utility).
        # The screen branches on the boolean and writes its own sentence.
        "background_available": ready,
        "filters": dict(filters),
        "unavailable": [dict(entry) for entry in PRINT_SET_UNAVAILABLE],
    }


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])  # A4: producing the file is a WRITE-shaped act
def print_sets(request: Any) -> Response:
    """`GET` — what a set would contain. `POST` — produce it.

    ⚠ **THE POST TAKES THE CALLER'S INSTANT AND READS NO CLOCK** (`BR-TEN-043`,
    gate G6 — there is no `timezone.now()` anywhere under `apps/billing/`). The
    archive's filename says when it was made, and a worker that picked the job
    up an hour later must not name the file with its own queue latency. The
    client sends `new Date().toISOString()`, exactly as the release gate does.
    """
    require_tenant(request)
    payload = _payload_of(request)
    filters = _filters_from(request, payload)

    if request.method == "GET":
        return Response(_preview(filters))

    # ⚠ **BORROWED, NOT COPIED, AND THE ALTERNATIVE IS WORSE.** `_datetime_field`
    # is where this product decides what counts as a valid instant — ISO-8601,
    # offset-bearing, a NAIVE timestamp REFUSED rather than assumed UTC, because
    # "2026-07-03T09:41" is a different moment in Houston than in Chennai. Writing
    # a second parser here would be a second answer to that question, and the day
    # the two disagreed one route would accept a stamp the other refuses.
    # `_actor_id` is the same argument for *"who is acting"*: the SESSION user,
    # never the body.
    #
    # Imported INSIDE the view and not at module scope so this file adds no
    # import-time dependency on `apps/billing/api.py` — the contended module this
    # one exists to stay out of. Underscore-prefixed and in the same module
    # (billing), which is the narrowest form of borrowing available.
    from apps.billing.api import _actor_id, _datetime_field

    generated_at = _datetime_field(payload, "generated_at")
    count = print_set.print_set_selection(filters).count()
    # CR-053 task 14 — the named format parameter. Taken from the body or the
    # query string, and REFUSED BY NAME when nobody has registered it: a print
    # vendor handed a file in a shape their loader does not read either stops,
    # which is a bad day, or reads the wrong field into the wrong place, which
    # is bills posted to the wrong people. There is no silent fallback here.
    try:
        chosen_format = print_formats.get(_format_from(request, payload))
    except BillingRuleError as broken:
        raise _refusal(broken) from broken

    # ⚠ **ONE RUN, IN ONE PROCESS — DEF-BIL-9152.** Until 2.455.1 the worker
    # was asked only when the caller sent `background: true`; without it the
    # request enqueued THROUGH THE TRANSPORT and then also ran the record
    # inline, so with a worker consuming billing's queue the set was built twice
    # and the web request answered 500. The decision is now the one every
    # billing job door makes (`check_api.run_check`): something consumes the
    # queue → hand it over and answer 202 (under JOBS_EAGER the transport runs
    # it in this process, once); nothing does → run it here, below. The flag
    # still decides only whether a fall-back to inline is worth a log line.
    wants_background = _wants_background(payload)
    ready, reason = print_set.would_run()
    if ready:
        try:
            record = print_set.enqueue_print_set(
                filters=filters,
                generated_at=generated_at,
                count=count,
                actor_user_id=_actor_id(request),
                format_name=chosen_format.name,
            )
        except BillingRuleError as broken:
            raise _refusal(broken) from broken
        return Response(
            {
                **core_jobs.accepted(record),
                "background": True,
                "bill_count": count,
                "format": chosen_format.name,
                "unavailable": [dict(entry) for entry in PRINT_SET_UNAVAILABLE],
            },
            status=202,
        )
    if wants_background:
        # NEVER QUEUED INTO A VOID (DEF-2487). Falling back to inline is safe
        # here in a way it is not for the 50,000-row import: the work IS DONE
        # when the response returns, and it is what this product would have done
        # anyway. The caller can tell from the status code.
        import logging

        logging.getLogger("smartbillhub.billing").warning(
            "print set asked for background and fell back to INLINE: "
            "nothing would have run it (%s)",
            reason,
        )

    try:
        print_set.refuse_if_oversized(count)
    except BillingRuleError as broken:
        raise _refusal(broken) from broken

    record = core_jobs.enqueue(
        print_set.PRINT_SET_JOB,
        payload={
            "filters": filters,
            "generated_at": generated_at.isoformat(),
            "count": count,
            "format": chosen_format.name,
            "actor_user_id": None if _actor_id(request) is None else str(_actor_id(request)),
        },
        scope_key=None,
        # ⚠ **HANDED TO NO TRANSPORT — THE RECORD IS THIS REQUEST'S OWN TO RUN
        # (DEF-BIL-9152).** Nothing consumes billing's queue (that is how this
        # line is reached), so a message sent there now is a SECOND run waiting
        # for the day a worker starts. The record exists only so the screen
        # polls one shape and the download route finds the file.
        dispatch=False,
    )
    core_jobs.run_pending(record["id"])
    return Response(
        {
            **core_jobs.accepted(record),
            "background": False,
            "bill_count": count,
            "format": chosen_format.name,
            "unavailable": [dict(entry) for entry in PRINT_SET_UNAVAILABLE],
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the same population the POST would hand over
def print_set_bills(request: Any) -> Response:
    """`GET /billing/print-sets/bills` — the bills in this period, one page.

    ⚠ **THE SCREEN HAD THE FORM, THE COUNTS AND THE BUTTON AND NO LIST**
    (`DEF-BIL-5354`). The blueprint's note names what that costs: *"A clerk's
    commonest question here is not how many — it is IS THIS CUSTOMER'S BILL IN
    THE SET, usually because that customer has rung. Without a searchable table
    the answer is generate it and look in the zip."*

    **ONE TABLE FOR THE WHOLE POPULATION, NOT TWO.** Every bill the selection
    holds is listed, each carrying whether it will print and, when it will not,
    the reason — because *"two tables would make a clerk searching for one bill
    look twice, and the counts would stop reconciling the moment a filter was
    applied."*

    **PAGED IN THE DATABASE, AND THE TOTAL COMES FROM IT** (`NFR-3`/`NFR-5`).
    At the top of the ICP a print set is tens of thousands of bills; the page is
    taken by `StandardPagination` and only the rows on screen are serialised or
    judged. The verdict costs ONE extra statement for the whole page —
    `forecast_rows` composes the address seam as a single `id__in` rather than
    asking it a row at a time.

    `status` IS NOT ACCEPTED HERE EITHER, for `print_set_selection`'s reason:
    the selection is issued and paid bills always, so a status control would
    offer a narrowing the server is about to override.
    """
    require_tenant(request)
    filters = _filters_from(request, {})
    params = selectors.list_params(request.query_params)
    selection = print_set.print_set_selection(filters, q=params.q)
    verdict = request.query_params.get("hold") or ""
    if verdict in (print_set.FORECAST_HELD, print_set.FORECAST_WILL_PRINT):
        selection = print_set.filter_by_forecast(selection, verdict)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(selection.select_related("account", "bill_run"), request)
    rows = list(page or [])
    verdicts = print_set.forecast_rows(rows)
    return paginator.get_paginated_response(
        [
            {
                # The S30 row, MOUNTED rather than re-serialised: a second row
                # shape for the same bill is two places for the account number,
                # the period and the money to drift apart.
                **selectors.invoice_row(invoice),
                "will_print": verdicts[str(invoice.id)] is None,
                "hold_reason": verdicts[str(invoice.id)],
                # An estimate, and only for a bill that will print. A held bill
                # has no page count because nothing will draw it, and the screen
                # renders that absence rather than a 0 — which would be a number
                # a print shop could quote against.
                "pages": (
                    print_set.MEASURED_PAGES_PER_BILL
                    if verdicts[str(invoice.id)] is None
                    else None
                ),
            }
            for invoice in rows
        ]
    )


urlpatterns = [
    path("billing/print-sets", print_sets),
    path("billing/print-sets/bills", print_set_bills),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-053 task 13 (12-governance/11-change-requests.md) + BR-NOT-029
#         (04-docs/05-modules/10-notifications/02-business-rules.md) + the PO
#         ruling of 2026-08-30 (12-governance/02-decision-log.md)
# generated: 2026-08-31 by the CR-053 W4 print-bills lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ py_compile✔ · tests/test_cr053_print_set.py · run_gates✔
#         (no new failure against the tip's own baseline) · golden-verify 33
#         PASS / 0 FAIL before and after — nothing on this path computes money.
#         RED PROVED FIRST: with this module's include removed from
#         config/urls.py the route does not resolve and the suite's selection
#         and preview cases fail on it; the failure is quoted in the lane report.
# exceptions: (1) NO DOWNLOAD VERB IS SERVED HERE. The finished archive is the
#         platform's `GET /api/exports/{job_id}/file`, which hands over a file
#         that already exists (a signed S3 link since 2026-10-02) — see the
#         module docstring on DEF-2734.
#         (2) THE INLINE PATH STILL CREATES A JOB RECORD, because the download
#         route resolves an artifact by JOB ID; an inline set with no record
#         would produce a file nobody could fetch. It is enqueued with NO scope
#         key, so an inline retry is a new record rather than a hand-back of a
#         finished one — the caller is standing there waiting for THIS file.
#         (4) `format` IS PUBLISHED AND NO SCREEN DRAWS A PICKER FOR IT.
#         There is one registered format, so a picker would be a control with a
#         single option — content for no decision (B14 rule 32). The list is on
#         the GET so the picker is a screen change and not a server change on
#         the day a second vendor shape is registered.
#         (3) `status` IS NOT AN ACCEPTED FILTER. A print set is issued and paid
#         bills (`print_set.PRINTABLE_STATUSES`); honouring `status=draft` would
#         produce an empty archive that reads like a broken renderer.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
