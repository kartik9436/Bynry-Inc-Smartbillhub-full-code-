# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (GET/POST /premises, PATCH, deactivate, delete guard) ·
#           US-MET-002 (GET /units, PATCH, deactivate) · US-MET-003
#           (POST /premises with nested units/assets · POST /units) ·
#           US-MET-004 (POST /premises/imports (+/commit) — CSV + pattern) ·
#           US-MET-005 (GET /routes · GET /cycles — read-only ops views) ·
#           US-MET-006 (routes/cycles CRUD + membership) · US-AST-011 /
#           US-AST-012 (`GET /reads/{id}.net_pair` — BR-AST-029's two records
#           served TOGETHER, which is what lets S29 draw them as a pair) ·
#           US-MET-013
#           (POST /reads/{id}/dispute + /dispute/clear — the S29 footer action
#           that had no endpoint, DEF-046)
#           CR-030 W5 tasks 5.2 + 5.3 (B18 §5.5.5 — GET /units/{id}/assets
#           and GET /units/{id}/pricing, both marked NEW there; NO STORY
#           OWNS EITHER — hard-won law 8, REPORTED)
#           CR-030 W6 task 6.12 (B18 §5.4.6 — GET /connections, the `NCT-01`
#           worklist S86's New connects tab had no endpoint for; NO STORY OWNS
#           IT either — hard-won law 8, REPORTED)
#           Screens: S14, S15, S16, S26, S27, S8, S25, S29, S86
# Rules:    BR-MET-024 (dispute = marker + reason; clear = System Admin only —
#           OQ-043 closure) · BR-MET-011 (S26/S27 never write) · BR-MET-035 (roles; server-
#           enforced per A4/BR-SHL-025) · BR-MET-036 (occupancy not settable) ·
#           BR-MET-046 (no cross-premises moves) · BR-SHL-011 (list grammar) ·
#           A11 Addendum r2 / 11b §2.5 + §2.3 (Routes & Cycles) + §2.7
# Tests:    06-backend/tests/test_us_met_*.py (API halves per story file) ·
#           06-backend/tests/test_w5_unit_reads.py (CR-030 W5 5.2/5.3) ·
#           06-backend/tests/test_w6_connection_list.py (CR-030 W6 6.12) ·
#           06-backend/tests/test_cr047_per_record_load.py (CR-047 — the two
#           result CSVs, and the `Accept: text/csv` negotiation DEF-553 broke)
# Impacts:  config/urls.py inclusion (wiring lane — `urlpatterns` exported here,
#           exactly as apps/tenancy/api.py does) · FI-01 typed client
# ───────────────────────────────────────────────────────
"""metering API endpoints per A11 as amended by 11b §2.5/§2.3/§2.7 (ratified
via A11 Addendum r2).

THIN by law (B8/LAW 0): every write goes through services (sole writer), every
read through selectors; no ORM here. Refusals are catalog exceptions rendered
by the BE-02 handler; role gates are the BE-04 permission classes AND the
service-layer @require_role guards (defense in depth, BR-SHL-025).

`urlpatterns` is exported for inclusion by config/urls.py — the include itself
is the platform wiring lane's one-liner (config/ is outside this packet's
territory; recorded in the build report).

Two deviations from the 11b row, both reported rather than resolved here:
- `DELETE /premises/{id}` and `DELETE /units/{id}` exist because the S14/S15
  capability matrices declare a Delete row action and BR-MET-037 defines its
  guard; 11b §2.5 lists only the deactivate verb.
- the bulk path is `POST /premises/imports` + `POST /premises/imports/commit`
  (no staged id): US-MET-004 §5 states the preview is computed with "no
  persistence in v1", so there is no batch row to address (E2 vs 11b's
  id-bearing 3-step contract).
"""

import logging
import math
import re
import time
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param

from apps.metering import (
    completeness,
    import_runs,
    read_import,
    read_rejects,
    read_windows,
    reading_sheet,
    seams,
    selectors,
    services,
    walk_order,
)

# ⚠ ALIASED, AND THE ALIAS IS LOAD-BEARING (DEF-713). `def connections(request)`
# below rebinds the bare name to the VIEW, so `connections.commit_connection`
# resolved against a function and raised AttributeError at request time on all
# three W6 write doors. ruff reported it as F811 and nothing read the report.
from apps.metering import connection_reads, monthly_usage_reads, quick_read

# MQ-033 (`CR-192-BRC10`) — aliased for DEF-713's reason: a module named like a
# view is one `def` away from being shadowed.
from apps.metering import read_formats as read_format_svc
from apps.metering import field_positions  # DEF-MET-10633 (FB-003)

# CR-039 wave C tasks 12-13. Aliased because `premises_owners` is also the
# name of the LIST VIEW below, and a module shadowed by a view function is
# how an import becomes silently unreachable at the bottom of a 2,000-line
# file.
from apps.metering import owner_selectors
from apps.metering import premises_owners as premises_owners_svc
from apps.metering import connections as w6_connections

# CR-094 wave 2 lane J — step 7's picker rows (hard-won law 2: it was built and
# reachable from no URL).
from apps.metering import connection_messages

# CR-126-BRC07 lane NCD-1 — the whole build record in one call, for the
# property's Build tab (OQ-MET-12520, closed 2026-09-21 on option C).
from apps.metering import connection_record

# ⚠ ALIASED FOR THE SAME REASON `connections` IS (DEF-713): `def asset_usage(
# request, asset_id)` below would rebind the bare module name to the VIEW, and
# `asset_usage.asset_usage_payload` would then resolve against a function and
# raise AttributeError at request time. The alias is load-bearing.
from apps.metering import asset_usage as asset_usage_reads
from apps.metering import unit_account as unit_account_reads  # CR-089 wave I
# CR-089 wave J. Aliased for DEF-713's reason even though no view here is
# called `move_preview` today: the next one added would shadow it silently.
from apps.metering import move_preview as move_preview_reads
# CR-094 capture lane E — the register's own address search (PO 2026-09-15).
from apps.metering import address_picker
from core import errors
from core.pagination import ListParams, StandardPagination, parse_list_params
from core.permissions import (
    SYSTEM_ADMIN,
    AdminOrClerk,
    AdminOrExecutive,
    AnyTenantRole,
    ConnectionsReadAnyWriteAdminOrClerk,
    SystemAdminOnly,
)
from core import tenancy as core_tenancy
from core.tenancy import require_tenant, stream_within_tenant_context, tenant_path


def _actor(request: Any) -> Any:
    """The acting user for the B12 §6a service shape: id from the session
    user, role server-attached by the identity layer — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="metering.payload_not_object")
    return data


# Per-screen capability-matrix vocabulary (BR-SHL-010/011): anything outside
# it falls back or is ignored — a list URL never 4xxs over its params.
# `area` — BR-MET-138 / DEF-836 (CR-039 wave E task 22). Same NAME as
# `ROUTE_FILTERS`' own area chip, deliberately: two spellings for one concept
# is how a shared URL stops working when it crosses a screen. An undeclared
# filter name is IGNORED by `parse_list_params`, which is why this list not
# carrying `area` made S14's area filter silently return the whole tenant
# rather than 400.
# ⚠ `location` IS DECLARED HERE OR IT IS SILENTLY DROPPED — `core.pagination.
# parse_list_params` documents that *"undeclared filter names are ignored"*, so
# a chip the client sends and this tuple does not name answers with the whole
# tenant and reads exactly like a filter that found everything (DEF-836 was that
# defect on `area`, and its check could not fail). CR-089 wave A `PUJ-01`.
# ⚠ `owner` JOINS THEM FOR THE SAME REASON `location` DID, AND IT CARRIES MORE
# WEIGHT: CR-089 wave B `B1` makes the owner optional at CREATE, so this filter
# is the only reader for the owner-less rows that reversal now allows. An
# undeclared name is DROPPED SILENTLY here, so a `Needs an owner` chip missing
# from this tuple would answer with the whole tenant and read exactly like a
# filter that found every property — which is DEF-836's defect, on the list it
# was found on. `B2`.
PREMISES_FILTERS = ("type", "status", "area", "location", "owner")
# `plan` — BR-MET-100: the Units tab MUST be able to list unplanned units
# ("unplanned" | "planned", resolved in selectors.units_list).
# `missing_services` — PO ruling 2026-09-28, verbatim: *"the Units 'Missing
# services' block — filter or leave it. - filter"*. Any truthy value asks for
# the units holding fewer service points than their address offers; it is the
# retired `GET /units/service-gaps` folded into the list it belongs on, which
# is what lets it combine with the search, with the other four filters and with
# the selection a bulk action reads.
UNIT_FILTERS = (
    "occupancy",
    "premises_id",
    "service",
    "sub_metered",
    "plan",
    "missing_services",
    # `CR-168-BRC10` image 14 — the raise's unit-type chips (lane SRV-2).
    "unit_type",
)
ROUTE_FILTERS = ("cycle", "type", "status", "service", "area", "on_cycle")  # CR-006
# `on_cycle` — DEF-MET-5743, SET-07 step 2's "already on a cycle" chip. `cycle`
# names ONE cycle and cannot ask "any", which is the question that step asks.
# CR-045 wave D task D.7 (DEF-1702) — `frequency` joins `status`. SET-05.cycles
# already draws a Frequency column and sorts on it (`CYCLE_SORTS["frequency"]`);
# it could not be FILTERED on, so the one dimension the tab most obviously
# offers was the one the server would not answer.
CYCLE_FILTERS = ("status", "frequency")


def _parsed(
    request: Any, sorts: tuple[str, ...], default_sort: str, filters: tuple[str, ...]
) -> ListParams:
    """The BR-SHL-011 params WITH `page` and `per` still on them.

    ⚠ **`_list_params` BELOW DROPS THOSE TWO, AND THAT WAS FINE ONLY WHILE THE
    PAGINATOR DID THE SLICING (`DEF-MET-5761`).** A selector that takes its own
    page in SQL has to be TOLD which page, so it needs the whole `ListParams`
    rather than the four keys a selector reading the whole set needs. Both
    readings come from ONE `parse_list_params` call so the two can never
    disagree about a fallback (hard-won law 1).
    """
    return parse_list_params(
        request.query_params,
        allowed_sorts=sorts,
        default_sort=default_sort,
        allowed_filters=filters,
    )


def _list_params(
    request: Any, sorts: tuple[str, ...], default_sort: str, filters: tuple[str, ...]
) -> dict[str, Any]:
    params = _parsed(request, sorts, default_sort, filters)
    return {
        "q": params.q,
        "filters": params.filters,
        "sort": params.sort,
        "direction": params.dir,
    }


def _page(request: Any, rows: Any, serializer: Any, prepare: Any = None) -> Response:
    """One page of `rows` in the DRF envelope, **without building the rest**.

    ⚠ **`list(rows)` STOOD WHERE `rows` NOW GOES, AND THAT ONE CALL IS THE WHOLE
    DEFECT (`DEF-MET-5761`).** PO, 2026-09-18: route setup and the premises list
    become unusable at 5,000–10,000 properties, and the same shape appears
    across the tables at 30–40,000 rows. `list()` drew **every row the tenant
    has** into memory and the paginator then threw all but fifty away — correct
    at the 79 properties of the demo utility, and `NFR-3`'s fifth breach at the
    top of T5 (40,000).

    Handed the result set itself, Django's paginator counts it with one
    `COUNT(*)` and slices it with `LIMIT`/`OFFSET`, so the read costs the PAGE
    and not the register. **Nothing here caps anything** — `NFR-5` is untouched,
    and `per` still clamps to the IS-2 vocabulary while `page` still clamps into
    range (`BR-SHL-011`: a list URL never 4xx-es over its params).

    ⚠ **IT WAS NOT MERELY A WASTED COPY ON ONE PATH.**
    `selectors.ReadArchiveResultSet` was built with `count()` and `__getitem__`
    precisely so the paginator could page the COLD store a partition at a time;
    `list()` reached its `__iter__` instead, which is `self[0:None]` — a SELECT
    over every detached partition **with no `LIMIT` clause at all**. The object
    was paginator-shaped and nothing ever paged it.

    ⚠ **A CALLER MAY STILL HAND OVER A PLAIN LIST, AND THREE DO.**
    `selectors.routes_page`, `selectors.cycles_page` and
    `completeness.pending_read_entries` each sort or derive on a figure no
    column holds and say so in their own docstrings. Those are **unchanged by
    this**: the paginator slices a list exactly as it did before, and removing
    `list()` only stops it copying one. Their own `NFR-3` remainder is
    `DEF-MET-5743`, and it is a different lane's.

    The serializer runs over the PAGE and never over the result set, exactly as
    it did before — so `premises`' `with_owner_account=False` discipline
    (`DEF-650` / `DEF-324`) is untouched and still costs what it did per row.

    ⛔ **`prepare` IS `BR-MET-1181`'s BATCH HOOK AND IT IS OPTIONAL.** Given one,
    it is called ONCE with the sliced page and its answer is handed to every
    row's serializer. **The only safe place to batch is here**, which is why this
    is a hook rather than a cache inside a serializer: a per-row serializer
    cannot see the page, so anything it memoises is still one statement per
    distinct value — on 200 properties with 200 different owners that is 200
    statements, the exact `DEF-324` shape this repository has now paid for twice.
    It runs AFTER the slice, so it reads the fifty rows on screen and never the
    register; `NFR-3` is untouched.
    """
    paginator = StandardPagination()
    page = list(paginator.paginate_queryset(rows, request) or [])
    if prepare is not None:
        prepared = prepare(page)
        return paginator.get_paginated_response([serializer(row, prepared) for row in page])
    return paginator.get_paginated_response([serializer(row) for row in page])


def _prepaged(
    request: Any,
    rows: list[dict[str, Any]],
    total: int,
    params: ListParams,
    refetch: Any,
    extra: dict[str, Any] | None = None,
) -> Response:
    """The SAME DRF envelope, over a page the SELECTOR already took (`NFR-3`).

    ⚠ **WHY `_page` COULD NOT BE REUSED FOR THE UNITS LIST.** `_page` hands its
    argument to the paginator, which needs something it can COUNT and SLICE.
    `selectors.units_list` cannot be that, because three of its filters —
    `occupancy`, `sub_metered` and `service` — partition on values no column
    holds (`BR-MET-036`: occupancy is DERIVED and there is no column to set),
    so a row has to exist before they can be read. `selectors.units_page` takes
    the page in SQL when it can and falls back to building the set when it must,
    and it says which in `units_list_is_sql_pageable`; what arrives here is
    already one page and the count is a `COUNT(*)`. This is
    `apps/customers/api.py`'s `_prepaged`, which `BR-CUS-1046` required for the
    accounts list — *"40,000 accounts built to draw fifty"* — and the shape is
    deliberately the same one.

    ⚠ **THE ENVELOPE IS BYTE-FOR-BYTE THE ONE EVERY OTHER LIST SERVES**:
    `count` / `next` / `previous` / `results`, with the links built by DRF's own
    `replace_query_param` so `?page=2` is formed here exactly as it is on the
    thirty endpoints that still go through the paginator. A second envelope
    shape on a list screen would be a client-side special case for ever.

    ⚠ **`page` IS RE-CLAMPED HERE AND NOT ONLY IN THE PARSER (`BR-SHL-011`).**
    `parse_list_params` clamps `page` to ≥ 1 and cannot know the LAST page — it
    has counted nothing yet. `StandardPagination.get_page_number` does that
    clamp for the paginator path; this path has to do it itself, or `?page=999`
    on a three-page list serves an empty `results` with a `previous` pointing at
    page 998 and the screen draws a blank table instead of the last page.
    """
    per = max(params.per, 1)
    pages = max(1, math.ceil(total / per)) if total else 1
    number = min(max(params.page, 1), pages)
    if number != params.page:
        # The clamp changed the page, so the rows we hold are the wrong ones.
        # Ask again for the page that exists rather than serving a blank table.
        rows, total = refetch(replace(params, page=number))
        pages = max(1, math.ceil(total / per)) if total else 1
    url = request.build_absolute_uri()
    following = replace_query_param(url, "page", number + 1) if number < pages and total else None
    if number > 2:
        preceding = replace_query_param(url, "page", number - 1)
    elif number == 2:
        preceding = remove_query_param(url, "page")
    else:
        preceding = None
    body: dict[str, Any] = {
        "count": total,
        "next": following,
        "previous": preceding,
        "results": rows,
    }
    for key, value in (extra or {}).items():
        body[key] = value
    return Response(body)


# ⚠ **`_asked_for_a_page` IS GONE — RC-W5-T6, 2026-08-23.** It answered *"did
# this caller ask for a page?"* and served a bare array to anyone who had not,
# because eight shipped call sites read `GET /routes` and `GET /cycles` as
# arrays and called `.filter`/`.find` on the answer: the cycle detail's Routes
# tab, both wizards, the S26/S27 ops tabs, the reads list, the upload-reads
# wizard and the BILL RUN's cycle picker. Answering the envelope unconditionally
# on the day RC-W3b landed would have broken all eight at runtime with every
# backend test still green.
#
# W5-T6 moved those call sites (`getRoutes()`/`getCycles()` ask for a page,
# unwrap `results` and follow `count` until they hold every row), so the
# transitional branch has no callers left and D7's ruling — *"Yes - please do
# it"* — is what these two endpoints now do without qualification. **ONE shape.**
# The pair of tests that hold it: `tests/test_cr029_rcw3b_endpoints.py::
# test_w3b_7__every_caller_gets_the_envelope_now_page_or_no_page` and
# `07-frontend/src/api/routesCyclesLists.cr029.test.ts`.


# ── S14 Premises (11b §2.5) ─────────────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # writes re-gated in services (BR-MET-035)
def premises(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        # `CR-161-BRC10` W2 — this route is Add Premises' door, so a required
        # custom field placed Input on S16 binds here (`DEF-MET-9226`).
        result = services.create_premises(
            _actor(request), _payload(request), custom_fields_screen="S16"
        )
        response = Response(result, status=201)
        response["Location"] = tenant_path(request, f"/premises/{result['id']}")
        return response
    params = _list_params(
        request,
        tuple(selectors.PREMISES_SORTS),
        selectors.PREMISES_DEFAULT_SORT,
        PREMISES_FILTERS,
    )
    # DEF-650 — the LIST does not expand each owner's ACCOUNT: one account read
    # plus one ledger derivation per row on one of the two screens a utility
    # opens most (DEF-324's measured N+1). `owner.master_account_id` is joined
    # and served; `owner.master_account_expanded` says the row did not ask.
    #
    # ⛔ **AND SINCE `BR-MET-1181` THE ROW PRINTS THE ACCOUNT NUMBER, WHICH IS
    # NOT THE SAME THING AND DOES NOT COST THE SAME THING.** B14 rule 31 forbids
    # a database id being the visible value of a field, so a column holding only
    # `master_account_id` had nothing it was allowed to draw.
    # `selectors.premises_master_account_numbers` answers **once for the whole
    # page** — a single `SELECT account_no … WHERE id IN (…)`, no ledger, no
    # balance — so the number rides free and the EXPANSION still does not happen.
    response = _page(
        request,
        selectors.premises_list(**params),
        lambda row, numbers: selectors.premises_detail_dict(
            row, with_owner_account=False, master_account_numbers=numbers
        ),
        prepare=selectors.premises_master_account_numbers,
    )
    response.data["rollup"] = selectors.premises_rollup()  # S14 header roll-up
    return response


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def premises_detail(request: Any, premises_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        # `CR-161-BRC10` W2 — Edit premise is the form that sends `custom_data`.
        return Response(
            services.update_premises(
                _actor(request),
                premises_id,
                _payload(request),
                custom_fields_screen="PREMISE_EDIT",
            )
        )
    if request.method == "DELETE":
        services.delete_premises(_actor(request), premises_id)
        return Response(status=204)
    return Response(selectors.premises_detail(premises_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # an ops READ, like the S26/S27 progress views
def premises_submeter_reconciliation(request: Any, premises_id: str) -> Response:
    """**CR-038 W6 — BR-MET-125's report: master vs Σ sub-meters, per period.**

    PO verbatim, 2026-08-26: *"Open 9 - (a) store + report — keeps the door
    open"*. The worked figure this reports: master **12,400 kWh** − Σ subs
    **11,940** = **460 kWh (3.71%)** against a **3%** tolerance.

    `?period=YYYY-MM` (or `YYYY-MM-DD`) narrows to one reading month; without it
    every stored period answers, newest first, with `periods` listing the months
    that actually have a row.

    **It serves STORED rows and recomputes nothing** — see the selector for why
    that is the point rather than a shortcut.

    House URL grammar (resource, then subpath). The A11 row for this route is
    OWED — see the exceptions trailer.
    """
    require_tenant(request)
    raw_period = str(request.query_params.get("period") or "").strip()
    period_month = None
    if raw_period:
        parsed = read_import._parse_date(raw_period) or read_import._parse_date(f"{raw_period}-01")
        if parsed is None:
            # Same reuse the chase list records: `metering.read_batch.period` is
            # the "reading month" fact this param carries, and minting a
            # thirteenth key in eleven catalogues for one query param is the
            # G32 zero-baseline ratchet pointing the wrong way. REPORTED there
            # and here.
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="metering.read_batch.period",
                field_errors=[
                    {
                        "field": "period",
                        "code": errors.VAL_FORMAT,
                        "message_key": "metering.read_batch.period",
                        "params": {},
                    }
                ],
            )
        period_month = parsed.date().replace(day=1)
    return Response(
        selectors.premises_submeter_reconciliation(premises_id, period_month=period_month)
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-MET-035: deactivate = System Admin
def premises_deactivate(request: Any, premises_id: str) -> Response:
    require_tenant(request)
    # `DEF-4743` — the payload rides through so this door records the same date
    # and reason the status dialog does. It used to send nothing and lose both.
    return Response(services.deactivate_premises(_actor(request), premises_id, request.data))


# ── CR-089 wave D · taking a property out of service (BR-MET-1164) ─────────
# PO 2026-09-08: *"Allow user to cahnge Unit and Premsies status"* — and until
# this landed NEITHER page had a control at all, only a badge.
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ: anyone who may see the property
def premises_status_change(request: Any, premises_id: str) -> Response:
    """What the status dialog draws BEFORE it asks: the live counts, whether the
    commit is held, and which count is holding it.

    ⚠ **A READ, DELIBERATELY SEPARATE FROM THE WRITE.** The counts have to be
    taken at the moment the dialog opens (BR-MET-1164 refuses on LIVE
    dependencies), and folding them into the premises detail payload would make
    every property page pay for four extra reads it does not draw.
    """
    require_tenant(request)
    return Response(selectors.premises_status_change(premises_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-MET-035: a status change = System Admin
def premises_status(request: Any, premises_id: str) -> Response:
    """`{status, effective_date, reason}` — all three required, both directions.

    The refusal, the date rules and the audit row are the SERVICE's; this view
    decides nothing.
    """
    require_tenant(request)
    return Response(services.change_premises_status(_actor(request), premises_id, _payload(request)))


# ── CR-039 wave C tasks 12-13 · premises owners (BR-MET-150/151) ────────────
# PO 2026-08-27, verbatim: *"category is okay, no richer text"*. Four surfaces,
# and the last is the one the ruling's own caveat asks for.
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # writes re-gated in the service (BR-MET-035)
def premises_owners(request: Any) -> Response:
    """The typed owner list and its create (BR-MET-150).

    `?q=` searches name, contact and the free-text string the party was matched
    FROM -- that last one is what makes the picker usable while BR-MET-151's
    matching backlog exists. `?active=true|false` narrows; absent means both,
    because a clerk auditing who was retired needs to see them.
    """
    require_tenant(request)
    if request.method == "POST":
        result = premises_owners_svc.create_premises_owner(_actor(request), _payload(request))
        response = Response(result, status=201)
        response["Location"] = tenant_path(request, f"/premises-owners/{result['id']}")
        return response
    raw_active = request.query_params.get("active")
    active = None if raw_active is None else raw_active.strip().lower() in ("1", "true", "yes")
    return _page(
        request,
        owner_selectors.owner_list(q=request.query_params.get("q"), active=active),
        # DEF-650 — the LIST does not expand each owner's account: that is one
        # account read plus one ledger derivation per row, and this endpoint
        # serves the picker 200 at a time (DEF-324's measured N+1). The row
        # carries `master_account_id` and `master_account_expanded: false`, so a
        # caller can tell *not asked* from *no account*; the detail endpoint and
        # `premises-owners/resolve` expand.
        lambda row: owner_selectors.owner_detail_dict(row, with_account=False),
    )


@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])
def premises_owner_detail(request: Any, owner_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        return Response(
            premises_owners_svc.update_premises_owner(_actor(request), owner_id, _payload(request))
        )
    return Response(owner_selectors.owner_detail_dict(premises_owners_svc._owner_row(owner_id)))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-MET-035: deactivate = System Admin
def premises_owner_deactivate(request: Any, owner_id: str) -> Response:
    require_tenant(request)
    return Response(premises_owners_svc.deactivate_premises_owner(_actor(request), owner_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_owners_resolve(request: Any) -> Response:
    """**DEF-650 — THE CHECK AT PREMISES CREATION, as an endpoint.**

    PO 2026-08-27: *"it can be existing master account also so at the time of
    premises creation we should check - how you will handle this"*. This is how:
    the wizard asks before it creates, and gets one of three answers.

    ``?name=Ridge Property LLC`` →
      ``{"match": "exact", "owner": {...}, "candidates": []}``  reuse this party
      ``{"match": "near",  "owner": null,  "candidates": [...]}``  the clerk picks
      ``{"match": "none",  "owner": null,  "candidates": []}``  nobody by that name

    GET and read-only: it takes no decision, it reports one. The clerk takes the
    decision, which is PO decision 3 (*"offer the match, clerk decides"*) made
    structural rather than promised in a comment.
    """
    require_tenant(request)
    return Response(premises_owners_svc.resolve_owner_name(request.query_params.get("name")))


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # re-gated in the service (BR-MET-035)
def premises_owner_master_account(request: Any, owner_id: str) -> Response:
    """**DEF-650 — declare the ACCOUNT this owner is billed through.**

    `{"account_id": "<uuid>"}` links; `{"account_id": null}` clears. It never
    creates an account: `accounts` is customers' table (B1/B2 §2), and the PO's
    own case is an account that ALREADY EXISTS.
    """
    require_tenant(request)
    return Response(
        premises_owners_svc.link_owner_master_account(
            _actor(request), owner_id, _payload(request).get("account_id")
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_owners_unmatched(request: Any) -> Response:
    """**PRM-04 - BR-MET-151's review surface, and it IS the flagged migration.**

    `metering 0040` writes no owner row, because the PO's caveat says so in as
    many words: *"They are real data on a live tenant. A flagged migration that
    offers each name for matching is the shape; silently guessing which string
    is which party is not."* This endpoint is the offer -- every free-text owner
    name that still points at no typed party, grouped BY NAME so twelve
    addresses sharing one landlord are one decision rather than twelve.

    It offers CANDIDATES and never a CATEGORY. `suggested_owner_ids` holds only
    exact case-insensitive name matches; a fuzzy suggestion is a guess wearing a
    suggestion's clothes, and a clerk working down a list will accept it.
    """
    require_tenant(request)
    rows = owner_selectors.unmatched_owner_rows()
    return Response(
        {
            "results": rows,
            "names": len(rows),
            "premises": sum(row["premises_count"] for row in rows),
        }
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # re-gated in the service (BR-MET-035)
def premises_match_owner(request: Any, premises_id: str) -> Response:
    """One address, one name, one person's decision (BR-MET-151).

    `{"owner_id": ...}` links an existing party; anything else CREATES one, and
    the caller always supplies the category. The premises' `owner_manager` is
    left exactly as it was -- it is the provenance of the match and what
    `open_account` reads for the default payer (`OQ-500`).
    """
    require_tenant(request)
    return Response(
        premises_owners_svc.match_premises_owner(_actor(request), premises_id, _payload(request))
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_types(request: Any) -> Response:
    """BR-MET-034: the premises-types Reference-data list. Served here because
    tenancy's LOOKUP_LISTS registry has no 'premises_types' key to register
    against (reported)."""
    require_tenant(request)
    return Response(selectors.premises_types())


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ of the register, like S14's list
def premises_picker(request: Any) -> Response:
    """`GET /premises/picker?q=&page=&per=` — **the register's own search, for
    any screen that PICKS an address rather than typing one.**

    PO ruling 2026-09-15: *"if we have unit or street address then we should
    take it from premises/Unit - it means its a search and if not foudn them
    alow user to add them"*. Capture step 3 is its first caller; move-in,
    transfer and the owner's-account path want the same search.

    ⚠ **THE QUERYSET IS HANDED TO THE PAGINATOR UNEVALUATED, AND THAT IS THE
    POINT.** `_page` above does `list(rows)` first, which pulls every premises
    the tenant has into memory before slicing — invisible at 79 properties and
    the shape of `NFR-3`'s existing breaches at the top of T5 (40,000). DRF
    slices a QuerySet with `LIMIT`/`OFFSET` and counts it with one `COUNT(*)`,
    so this read costs the page and not the register.

    Nothing about meters, services or accounts is in the answer — the same
    ruling's second clause puts those on the move-in request.
    """
    require_tenant(request)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(
        address_picker.search(q=request.query_params.get("q")), request
    )
    return paginator.get_paginated_response(address_picker.page_rows(page))


# ── S15 Units (11b §2.5) ────────────────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def units(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        result = services.create_unit(_actor(request), _payload(request))
        response = Response(result, status=201)
        response["Location"] = tenant_path(request, f"/units/{result['id']}")
        return response
    params = _parsed(
        request, tuple(selectors.UNIT_SORTS), selectors.UNIT_DEFAULT_SORT, UNIT_FILTERS
    )
    # CR-089 wave E (`E1`/`PUJ-22`) — the OWED column. `_page` is not used here
    # because the money has to be resolved ONCE for the page and `_page`'s
    # serializer runs per row; `unit_list_rows` is the page-shaped serializer
    # and this is the only call site that needs it.
    #
    # ⚠ **AND THE PAGE IS TAKEN IN SQL SINCE `DEF-MET-5761`.** This read was
    # `paginate_queryset(list(selectors.units_list(**params)), …)`, which built
    # EVERY unit the tenant has — and then, through `unit_list_rows`, resolved
    # the ledger for the fifty that survived. `selectors.units_page` takes the
    # page itself and returns `(rows, total)`; `_prepaged` serves the identical
    # envelope over it. The ONE ledger read per page is unchanged and is still
    # the reason this endpoint has its own serializer.
    rows, total = selectors.units_page(params)
    # ── `service_gap_count` — PO ruling 2026-09-28 ──────────────────────────
    # ⚠ **THE COUNT IS THE DELIVERABLE, NOT THE FILTER CONTROL.**
    # `DEF-MET-6796` exists because the shortfall was INVISIBLE, and a filter
    # nobody switches on is invisible in the same way. So the figure rides
    # THIS envelope on every read — the toolbar draws it whether or not the
    # filter is engaged — rather than arriving from a second request the
    # screen would have to remember to make.
    #
    # ⚠ **ONE `COUNT(*)`, NOT A SECOND PAGE OF ROWS.** The retired
    # `GET /units/service-gaps` built fifty rows to show a number; this builds
    # none. `units_gap_count` ignores `missing_services` and honours
    # everything else, so switching the filter on does not change the number
    # beside the control.
    return _prepaged(
        request,
        rows,
        total,
        params,
        refetch=selectors.units_page,
        extra={"service_gap_count": selectors.units_gap_count(params)},
    )


# ── `GET /units/service-gaps` — RETIRED 2026-09-28 ──────────────────────────
# PO, verbatim: *"the Units 'Missing services' block — filter or leave it. -
# filter"*. `units_service_gaps` stood here and served the block's own page of
# rows. It is DELETED rather than deprecated, because a second door onto one
# set is how the two drift apart — the whole reason the PO closed it. Its
# question is now `?f.missing_services=yes` on `GET /units` above, and its
# count is `service_gap_count` in that read's own envelope.
#
# ⚠ **THE CONSUMERS WERE WALKED BEFORE IT WENT (hard rule 8's lesson).** One
# client called it — `getUnitServiceGaps` in `07-frontend/src/api/endpoints.ts`,
# from `UnitServiceGaps.tsx`, from the units list. All three are gone in the
# same commit. `test_a3_the_route_is_no_longer_registered` asserts the address
# is absent, so a client left calling it cannot be answered by a silent 404
# with every test green.

@api_view(["GET"])
@permission_classes([AnyTenantRole])
def unit_number_preview(request: Any) -> Response:
    """CR-089 wave E (`E6`/`PUJ-26`) — the numbers the review shows.

    `BR-MET-1165`: **the number is taken on the press, never reserved by the
    preview.** This endpoint therefore allocates nothing, advances nothing and
    locks nothing — two clerks reviewing at the same moment are both shown the
    same next number, and the second one to press gets the one after it. The
    rule and its reasoning are in `services.preview_unit_numbers`.
    """
    require_tenant(request)
    try:
        count = int(request.query_params.get("count") or 1)
    except (TypeError, ValueError):
        count = 0
    return Response(services.preview_unit_numbers(count))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premise_number_preview(request: Any) -> Response:
    """CR-089 wave B (`B7`/`PUJ-08`) — the premise number the review shows.

    The premises twin of `unit_number_preview` above and the same rule
    (`BR-MET-1165`): it allocates nothing, advances nothing and locks nothing.
    Two clerks reviewing at the same moment are both shown `P-00080`; the second
    to press gets `P-00081`. The reasoning, and why it does not read
    `number_series.next_number` directly, is in `services.preview_premise_number`.
    """
    require_tenant(request)
    return Response(services.preview_premise_number())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_same_address(request: Any) -> Response:
    """`GET /premises/same-address?address_line=&city=&state=&postal_code=` —
    `CR-177-BRC10` task 1 · `BR-MET-1190`.

    `{"same": {premise_no, address, units, status, id} | null}`. The screen asks
    it as the clerk completes the address; `create_premises` asks the SAME
    function again at the write, so the two cannot disagree. A pure read, scoped
    to the tenant (hard rule 1). `id` is for the *Open it* link only (B14 rule
    31); the premise NUMBER and the address are what a clerk reads.
    """
    require_tenant(request)
    from apps.metering import address_match

    params = request.query_params
    same = address_match.premises_with_same_address(
        params.get("address_line"),
        params.get("city"),
        params.get("state"),
        params.get("postal_code"),
    )
    if same is None:
        return Response({"same": None})
    return Response(
        {
            "same": {
                "id": same["id"],
                "premise_no": same["premise_no"],
                "address": services.compose_address(
                    same["address_line"], same["city"], same["state"], same["postal_code"]
                ),
                "units": same["units"],
                "status": same["status"],
            }
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_owner_search(request: Any) -> Response:
    """`GET /premises/owner-search?q=&page=&per=` — `CR-177-BRC10` task 1b.

    The utility's MASTER accounts by name or account number, PAGED (NFR-3, no
    cap): account number, name, account type, person or company, managed by,
    status. Customers answers the account half through metering's read-only
    seam; **Managed by is metering's own fact** — the `owner_manager` recorded
    on the premises this account already owns — read once for the page.
    """
    require_tenant(request)
    found = seams.master_account_search(request.query_params.get("q"))
    if found is None:
        return Response({"count": 0, "next": None, "previous": None, "results": []})

    def prepare(page: Any) -> dict[str, Any]:
        rows = seams.master_account_search_rows(page)
        managed = selectors.managed_by_for_master_accounts(list(rows))
        return {"rows": rows, "managed": managed}

    def serialise(account: Any, prepared: dict[str, Any]) -> dict[str, Any]:
        row = dict(prepared["rows"].get(str(account.id)) or {"id": str(account.id)})
        row["managed_by"] = prepared["managed"].get(str(account.id))
        return row

    return _page(request, found, serialise, prepare=prepare)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_lends(request: Any, premises_id: str) -> Response:
    """CR-089 wave E (`E3`/`PUJ-23`) — what a building lends to the units added
    to it: its identity, what is on it today, the services it offers and the
    routes its units join. A pure read; see `selectors.premises_lends_dict`."""
    require_tenant(request)
    return Response(selectors.premises_lends_dict(selectors.premises_row(premises_id)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def premises_units_next_free(request: Any, premises_id: str) -> Response:
    """`CR-176-BRC10` rule (1) — the first number from which a run of
    `count` units (× `floors`, labelled by `label_pattern`) is wholly free at
    this building. The Add units screen defaults *Start numbering at* to it and
    prints *Next free: N*. A pure read: nothing is reserved, so two clerks may
    both be told 6 and the second press is refused naming the labels — the
    same posture `BR-MET-1165` takes for unit numbers."""
    from apps.metering import importers

    require_tenant(request)
    premises = selectors.premises_row(premises_id)

    def _positive(name: str, default: int) -> int:
        raw = request.query_params.get(name)
        try:
            value = int(raw) if raw not in (None, "") else default
        except (TypeError, ValueError):
            value = default
        return value if value >= 1 else default

    pattern = str(request.query_params.get("label_pattern") or "").strip() or "{seq}"
    floors = _positive("floors", 1)
    per_floor = _positive("count", 1)
    taken = importers.existing_unit_labels(premises)
    # `start` is optional: given, the answer also names which labels of THAT
    # run are already on file — the sentence the screen prints under *Start
    # numbering at* before Continue is pressed.
    start = _positive("start", 1) if request.query_params.get("start") else None
    clashing = (
        [
            label
            for label in importers.run_labels(
                pattern, floors=floors, per_floor=per_floor, floor_start=1, seq_start=start
            )
            if label.lower() in taken
        ]
        if start is not None
        else []
    )
    return Response(
        {
            "next_free": importers.next_free_seq_start(
                premises, label_pattern=pattern, floors=floors, per_floor=per_floor, taken=taken
            ),
            "taken": clashing,
        }
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def unit_detail(request: Any, unit_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        # `CR-161-BRC10` W2 — Edit unit is the form that sends `custom_data`.
        return Response(
            services.update_unit(
                _actor(request), unit_id, _payload(request), custom_fields_screen="UNIT_EDIT"
            )
        )
    if request.method == "DELETE":
        services.delete_unit(_actor(request), unit_id)
        return Response(status=204)
    # CR-089 wave F `F3` — the S15 row PLUS the three tile figures. The four
    # tiles ride the payload this page already asks for, so they cost no extra
    # request on load and none on any of the five tab changes; the LIST and
    # every internal caller keep `unit_list_dict` unchanged. See
    # `selectors.unit_page_dict` for the cost that was designed rather than
    # discovered.
    return Response(selectors.unit_page_dict(selectors.unit_row(unit_id)))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def unit_deactivate(request: Any, unit_id: str) -> Response:
    require_tenant(request)
    # `DEF-MET-4761` — the payload rides through so this door records the same
    # date and reason the status dialog does. It used to send nothing and lose
    # both, which is `DEF-4743` one level down.
    return Response(services.deactivate_unit(_actor(request), unit_id, request.data))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # CR-089 wave D — a READ, like the premises one
def unit_status_change(request: Any, unit_id: str) -> Response:
    """The unit's live dependency counts, for the status dialog (`PUJ-48`)."""
    require_tenant(request)
    return Response(selectors.unit_status_change(unit_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-MET-035
def unit_status(request: Any, unit_id: str) -> Response:
    """`{status, effective_date, reason}` — BR-MET-1164 one level down."""
    require_tenant(request)
    return Response(services.change_unit_status(_actor(request), unit_id, _payload(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-MET-035: a move is an EDIT, not a deactivation
def unit_move(request: Any, unit_id: str) -> Response:
    """BR-MET-095 (CR-024): move a unit to another premise, as a dated event.

    A correction, not a deactivation — so it takes the create/edit role pair
    BR-MET-035 names rather than `SystemAdminOnly`. Every refusal (no reason, no
    date, a FUTURE date, the same premise, a colliding label, an un-acknowledged
    unit that has had accounts) is the SERVICE's; this view decides nothing.
    """
    require_tenant(request)
    return Response(services.move_unit(_actor(request), unit_id, _payload(request)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ, like the status-change one above
def unit_move_preview(request: Any, unit_id: str) -> Response:
    """`GET /units/{id}/move-preview?premises_id=` — CR-089 wave J (`PUJ-46`).

    **WHAT MOVING THIS UNIT WILL DO, ITEMISED, BEFORE ANYBODY PRESSES ANYTHING.**
    The screen used to describe the consequence in two sentences and neither of
    them mentioned the two that travel furthest: every asset tagged to the unit
    changes address with it (an address is stored on `premises` and nowhere
    else), and the route and cycle change, so a different person reads the meter
    on a different day.

    `?premises_id=` is OPTIONAL. Without it the answer is the *from* side only —
    what the unit carries today — which is what the screen draws before a
    destination has been chosen. Unknown or foreign ids on either side are a 404
    through the selectors, never a preview of absences.

    ⛔ **IT DECIDES NOTHING AND APPROVES NOTHING.** `POST /units/{id}/move` still
    owns every refusal, this endpoint duplicates none of them, and a preview and
    a refusal that disagree are the refusal being right.
    """
    require_tenant(request)
    return Response(
        move_preview_reads.move_preview(unit_id, request.query_params.get("premises_id") or None)
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def unit_plan_assignments(request: Any, unit_id: str) -> Response:
    require_tenant(request)
    return Response(
        services.assign_unit_plan(_actor(request), unit_id, _payload(request)), status=201
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def unit_plan_assignments_bulk(request: Any) -> Response:
    require_tenant(request)
    return Response(services.bulk_assign_unit_plans(_actor(request), _payload(request)))


# ── S16 bulk (11b §2.5 — pattern generator + CSV) ───────────────────────────
@api_view(["POST"])
@permission_classes([AnyTenantRole])
def premises_imports(request: Any) -> Response:
    """Staged preview: every row validated, NOTHING written (BR-MET-004)."""
    require_tenant(request)
    return Response(services.stage_import(_actor(request), _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def premises_imports_commit(request: Any) -> Response:
    """Commit with skip-errors ON by default; the "N created · N failed"
    summary is ALWAYS in the body (BR-MET-038)."""
    require_tenant(request)
    return Response(services.commit_import(_actor(request), _payload(request)), status=201)


# ── S26/S27 ops views + S8 Routes & Cycles config (11b §2.7 / §2.3) ─────────
class RoutesConfigAccess(AnyTenantRole):
    """BR-MET-035b — READ for any tenant role, WRITE for System Admin only.

    ⚠ **BOTH GATES, DELIBERATELY.** The service functions already carry
    `@require_role(SYSTEM_ADMIN)`, so this class is the second of two — and
    CR-005 proved why a second is not redundant: its permission test stayed
    GREEN with the endpoint's gate deleted, because the service refused
    underneath, and a test that cannot tell the two apart is a test that
    protects neither. The endpoint refuses at the door with the right HTTP
    status; the service refuses whoever calls it from anywhere.

    Read stays open to every tenant role because the S26/S27 ops tabs read
    these same endpoints (BR-MET-011), and a Billing Clerk must be able to see
    which route a premises is on. What they may not do is change it.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return super().has_permission(request, view)
        return SystemAdminOnly().has_permission(request, view)


@api_view(["GET", "POST"])
@permission_classes([RoutesConfigAccess])  # BR-MET-011 read · BR-MET-035b write
def routes(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(services.create_route(_actor(request), _payload(request)), status=201)
    # CR-029 D7 (*"Yes - please do it"*) — SERVER-SIDE paging and sorting, in
    # BR-SHL-011's grammar, for EVERY caller. `q/sort/dir/page/per/f.*` are
    # honoured and the answer is always the `{count, next, previous, results}`
    # envelope; the transitional bare-array branch retired with W5-T6 (note
    # above `routes`' paging helpers).
    rows = selectors.routes_page(
        **_list_params(
            request, tuple(selectors.ROUTE_SORTS), selectors.ROUTE_DEFAULT_SORT, ROUTE_FILTERS
        )
    )
    return _page(request, rows, lambda row: row)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def route_next_code(request: Any) -> Response:
    """BR-MET-073 — the code SET-06 step 1 pre-fills, EDITABLE. A preview, so
    opening the wizard and cancelling does not burn a number."""
    require_tenant(request)
    return Response(services.next_route_code())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def cycle_next_code(request: Any) -> Response:
    """BR-MET-077 — the same, for SET-07 step 1."""
    require_tenant(request)
    return Response(services.next_cycle_code())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def route_premises_picker(request: Any) -> Response:
    """SET-06 step 2 — the dual-pane picker's left side (BR-MET-072/074).

    `area` repeats for a multi-select (`?area=NORTH&area=SOUTH`), which is
    how the "1 to many" ruling reaches the wire; absent = All.

    ⚠ **IT ANSWERS THE `{count, results}` ENVELOPE AND IT PAGES SERVER-SIDE
    (`DEF-MET-5743`, `NFR-3`).** It served a BARE ARRAY of every matching
    premises in the tenant until 2026-09-18, built with one `Unit` query and
    one `assets_on_unit` call per row — correct at the <3,000-connection
    ceiling this product was scoped to until 2026-09-06, and 13× short of T5's
    40,000. The PO's own words for what it cost: *"Route setup becomes
    unusable at 5,000–10,000 premises"*.

    ⚠ **AND `per` CARRIES NO MAXIMUM (`NFR-5`).** Omitting it still returns
    every matching row, so nothing here is a cap that would have to be removed
    when T4 arrives; what is added is the ABILITY to ask for a window and be
    told the true total beside it. The screen asks for one; an export or a
    test may still ask for all of them.

    `sort`/`dir` are `BR-SHL-011`'s grammar, over the vocabulary
    `selectors.PREMISES_PICKER_SORTS` declares — an unknown key falls back to
    the default rather than erroring, as `/routes` and `/cycles` already do.

    `members=1` narrows to the premises already on `route_id`. That is the
    EDIT path: re-opening a route must re-tick its own members, and with a
    paged picker those rows are mostly not on the page in front of you. It is
    bounded by the route rather than by the tenant (`BR-MET-055`).
    """
    require_tenant(request)
    params = request.query_params
    per = params.get("per")
    return Response(
        selectors.route_premises_picker_page(
            q=params.get("q"),
            areas=params.getlist("area"),
            service=params.get("service"),
            unassigned_only=params.get("unassigned") in ("1", "true", "yes"),
            route_id=params.get("route_id"),
            members_only=params.get("members") in ("1", "true", "yes"),
            sort=params.get("sort"),
            direction=params.get("dir") or "asc",
            page=_positive_int(params.get("page"), 1),
            per=None if per in (None, "", "all") else _positive_int(per, 50),
        )
    )


def _positive_int(value: Any, fallback: int) -> int:
    """A query-string integer, or the fallback — never an exception.

    A bookmarked URL carrying `page=` or `per=junk` is an ordinary thing for a
    browser to send, and the same reasoning `_area_predicate` records applies:
    the screen can render a first page, so it gets one. **It does NOT clamp to
    an upper bound** — `NFR-5`, and the docstring above.
    """
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def route_meter_picker(request: Any) -> Response:
    """SET-06 step 3 — the meters the chosen premises bring (BR-MET-075).

    ⚠ **`unit_id` IS GONE AND `premises_id` REPLACES IT (`CR-131-BRC07`).** The
    wizard sent one `unit_id` per unit: **37,994 characters at 726 units**
    against a 4–8 KB limit, so the request never arrived and step 3 drew its
    empty state over a route full of meters. A saved route now sends nothing
    but `route_id`; an open wizard sends the **6** premises it has ticked.

    ⚠ **A `unit_id` PARAMETER IS NOT SILENTLY IGNORED — it is REFUSED BY
    NAME.** Accepting and dropping it would give a caller that had not been
    updated an empty meter list and no reason, which is the same false absence
    the whole of this change exists to remove. `BR-SHL`'s posture: a request
    this endpoint cannot honour says so.
    """
    require_tenant(request)
    params = request.query_params
    if params.getlist("unit_id"):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="metering.route.meter_picker_unit_id_retired",
            params={
                "detail": (
                    "This list is asked for by premises now. Send route_id for a "
                    "saved route, or premises_id for a selection that is not saved "
                    "yet."
                )
            },
        )
    per = params.get("per")
    return Response(
        selectors.route_meter_picker(
            route_id=params.get("route_id"),
            premises_ids=params.getlist("premises_id"),
            page=_positive_int(params.get("page"), 1),
            # `all` serves the whole set — NFR-5: no hard cap. It is the
            # caller's word, not a number this endpoint clamps.
            per=None if per in ("", "all") else _positive_int(per, 50),
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def cycle_coverage(request: Any) -> Response:
    """SET-07 step 3 — BR-MET-080's *"47 accounts unscheduled"*, computed
    INCLUDING the routes step 2 has just selected."""
    require_tenant(request)
    # CR-029 — the same call now also answers WHICH accounts (SET-07D's
    # Coverage tab listed nothing because this endpoint served a count and
    # nothing else). ⚠ D13: each row names what it LACKS — a route — and no
    # assign-a-cycle action exists anywhere to go with it.
    return Response(selectors.uncovered_account_count(request.query_params.getlist("route_id")))


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([RoutesConfigAccess])  # BR-MET-035b
def route_detail(request: Any, route_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        return Response(services.update_route(_actor(request), route_id, _payload(request)))
    if request.method == "DELETE":
        services.delete_route(_actor(request), route_id)
        return Response(status=204)
    return Response(selectors.route_detail(route_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def route_reader(request: Any) -> Response:
    """MQ-033 (PO 2026-10-24) — set or clear the reader on one or many routes,
    from Reads → cycle → Routes: `{"route_ids": [...], "reader_id": <uuid>|null}`.

    ⚠ **OFFICE ROLES THAT DO THE DAY'S WORK — ADMIN AND CLERK.** Who walks a
    route this month is reading WORK, which `BR-MET-011` as narrowed makes
    writable on the Reads screen; the route's DEFINITION stays System Admin's
    in Settings. An executive reads; a field technician never reaches this.
    The service is `route_readers.set_reader` and its docstring says what it
    refuses and why."""
    require_tenant(request)
    from apps.metering import route_readers

    return Response(route_readers.set_reader(_actor(request), _payload(request)))


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def route_reader_choices(request: Any) -> Response:
    """MQ-033 — the reader picker: this tenant's ACTIVE field technicians,
    `?q=` matching name or email, paged in SQL (NFR-3, nothing capped)."""
    require_tenant(request)
    from apps.metering import route_readers

    return _page(
        request,
        route_readers.reader_choices_queryset(request.query_params.get("q")),
        route_readers.reader_choice_row,
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def route_deactivate(request: Any, route_id: str) -> Response:
    require_tenant(request)
    return Response(services.deactivate_route(_actor(request), route_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a clerk PRINTS the sheet; nothing writes
def route_sheet_view(request: Any, route_id: str) -> Any:
    """CR-038 W5 — the RDS-01 header button, finally live: the printable route
    sheet, served as PRINT-READY HTML (a self-contained page with its own
    @media print stylesheet).

    NOT PDF bytes, and that is a recorded lane decision, not an oversight: no
    PDF library is a backend dependency, adding one is not a lane's call, and
    the one hand-rolled PDF writer in the product is billing's own module
    scoped to the bill document (see apps/metering/route_sheet.py's docstring).
    The browser's Print / Save as PDF is the "PDF" the r10 button promises.

    Opens in its own tab from S25 (the same same-origin-anchor pattern the
    bill's `/document.pdf` uses), so the session cookie rides along and HR-1's
    one 404 covers an unknown, malformed or cross-tenant route id.
    """
    require_tenant(request)
    from django.http import HttpResponse

    from apps.metering import route_sheet

    html = route_sheet.render_route_sheet(route_id)
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a clerk PRINTS the sheet; nothing writes
def cycle_sheet_view(request: Any, cycle_id: str) -> Any:
    """BR-MET-162 (DEF-898) — **the same sheet, asked for by CYCLE.**

    PO 2026-08-27: *"allow route of Cycle - both"*. The route sheet already
    printed its cycle in its own header, so the cycle was a first-class fact of
    the artefact with **no way to ask for one** — and a monthly walk is
    organised by cycle as often as by route.

    ⚠ **A MISSING ENTRY POINT IS INVISIBLE TO EVERY TEST THAT ONLY EXERCISES
    THE ENTRY POINT THAT EXISTS**, which is why this shipped half-built and
    green: every test asked for a route sheet by route and got one.

    Same content, same print-ready HTML, same `AnyTenantRole` read, same HR-1
    single 404 for an unknown, malformed or cross-tenant id. The body is
    SECTIONED by route because a walk order belongs to a route (D11) and no
    ruled ordering exists across routes.
    """
    require_tenant(request)
    from django.http import HttpResponse

    from apps.metering import route_sheet

    html = route_sheet.render_cycle_sheet(cycle_id)
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@api_view(["PUT"])
@permission_classes([RoutesConfigAccess])  # BR-MET-035b — write is System Admin
def route_premises_order(request: Any, route_id: str) -> Response:
    """CR-029 D3 + D11 — **the walking order, per premises**.

    SET-06D's drag-to-reorder has POSTed here since it shipped and got a 404,
    because RC-W1 landed `route_premises_orders` and mounted no path (B17 §5
    gap G5: *"exists with a uniqueness constraint and NO WRITER"*). This is
    the door.

    The body is `{"order": [{"premises_id": …, "walk_order": N}, …]}` — what
    `walkOrderPayload()` already sends — and a bare list of premises ids is
    accepted too, position first. The whole walk travels: a list that omits or
    repeats a member is refused before anything is written.

    ⚠ **PUT ONLY, AND THE MISSING GET IS DELIBERATE.** `GET /routes/{id}`
    already serves `premises_order`, so a second read of the same fact would be
    a route with no caller — the mirror of the defect this wave exists to fix
    (hard-won law 2), and a second place for the stop list to be right or wrong.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        walk_order.save_premises_order(
            _actor(request), route_id=route_id, order=payload.get("order", payload)
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # BR-MET-011 — the ops tabs read this too
def route_read_windows(request: Any, route_id: str) -> Response:
    """CR-029 D1 — SET-06D's **Read history**: Window · Read on · Reader ·
    Collected · Expected · Result, newest walk first.

    `read_windows` became a first-class closable record in RC-W1-T4 and RC-W2
    wrote the closer; nothing served the rows, so the Audit tab said so rather
    than drawing six empty columns. `limit` clamps into 1…200 (BR-SHL-011's
    never-error posture) and defaults to 50, the one page size this product
    already uses everywhere.

    ── W5-T6 ASKED WHETHER THIS JOINS THE PAGED GRAMMAR. IT DOES NOT. ────────
    B17 §7 W5-T6 leaves the choice open and asks for the answer to be stated,
    so: **`limit`, no `page`, and this is a bounded HISTORY rather than a
    list.** Three reasons, none of them "later".

      1. There is no pager on the surface. SET-06D's Read history is a card
         inside a tab that renders the most recent walks; a `{count, next}`
         envelope would describe navigation no control offers, which is
         hard-won law 2 (a payload no screen reads).
      2. `count` would cost a second query per open of the tab to answer a
         question nobody asks. The rows are answered newest-first and the
         honest claim is *"the last N"*, which `limit` states exactly.
      3. Page 2 of a history that grows at the top is not stable. A crew
         closing a window between two requests shifts every row down one, so a
         paged read history serves duplicates and skips — the same reason
         `GET /billing/runs` keeps this posture.

    If a screen ever needs to walk the whole history, that is a different
    endpoint shape (a keyset cursor on `period_start`), not this one with a
    `page` param bolted on.
    """
    require_tenant(request)
    try:
        limit = int(str(request.query_params.get("limit", 50)))
    except (TypeError, ValueError):
        limit = 50
    limit = min(max(limit, 1), 200)
    # The route is resolved (and tenant-checked) before its history is read —
    # an unknown or foreign id is ABSENT, never an empty list that would read
    # as "this route has never been walked".
    selectors.route_row(route_id)
    return Response({"windows": read_windows.read_window_history(route_id, limit=limit)})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def route_accounts(request: Any, route_id: str) -> Response:
    """SET-06D's **Accounts** tab — *"the accounts a missed read here affects"*.

    ⚠ **STATUS ONLY (D12, *"not required"*).** The screenshot draws a Balance
    column; routes and cycles are grouping only (BR-MET-078, hardened by this
    CR), so no money reaches this payload — asserted by test, not by eye.

    The accounts come through the reviewed customers seam
    (`apps/metering/seams.py`), one batched read for the whole route rather
    than `GET /accounts?unit_id=` once per unit (D7).
    """
    require_tenant(request)
    return Response(selectors.route_accounts(route_id))


@api_view(["GET", "POST"])
@permission_classes([RoutesConfigAccess])  # BR-MET-035b
def cycles(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(services.create_cycle(_actor(request), _payload(request)), status=201)
    rows = selectors.cycles_page(  # CR-029 D7 — as `routes` above
        **_list_params(
            request, tuple(selectors.CYCLE_SORTS), selectors.CYCLE_DEFAULT_SORT, CYCLE_FILTERS
        )
    )
    return _page(request, rows, lambda row: row)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([RoutesConfigAccess])  # BR-MET-035b
def cycle_detail(request: Any, cycle_id: str) -> Response:
    """⚠ **GET LANDED IN CR-029 RC-W3b** — this route was PATCH+DELETE only,
    so SET-07D and its editor each read the WHOLE `GET /cycles` list and picked
    their row out of it. The GET serves `cycle_dict` unchanged (the list row's
    own shape, schedule proposal included), so the screen renders with nothing
    else edited the day it calls this."""
    require_tenant(request)
    if request.method == "DELETE":
        services.delete_cycle(_actor(request), cycle_id)
        return Response(status=204)
    if request.method == "PATCH":
        return Response(services.update_cycle(_actor(request), cycle_id, _payload(request)))
    return Response(selectors.cycle_detail(cycle_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # BR-MET-011 — an ops READ, like S26/S27
def cycle_chase_list(request: Any, cycle_id: str) -> Response:
    """CR-038 W1 — BR-MET-057's chase list (US-MET-018): the cycle's meters
    still missing plan-required registers, each named channel by channel, with
    unit · premises · meter · route · service · days left — ordered days-left
    asc then unit label, shaped for the CSV export a later lane wires (IS-9).

    `?period=YYYY-MM-DD` (or `YYYY-MM`) names the reading month; without it
    the CURRENT window answers. Before window open the list is EMPTY with
    `window_opens` saying when — US-MET-018 TC-6's *"window opens Aug 12"*,
    never pending pressure ahead of the window. Bounded by the cycle's own
    membership (BR-MET-055 — this can never exceed the cycle's meters).

    House URL grammar (resource, then verb-as-subpath); the A11 row for this
    route is OWED — see the exceptions trailer.
    """
    require_tenant(request)
    cycle = selectors.cycle_row(cycle_id)  # tenant-scoped; foreign/unknown = 404
    raw_period = str(request.query_params.get("period") or "").strip()
    period_anchor = None
    if raw_period:
        parsed = read_import._parse_date(raw_period) or read_import._parse_date(f"{raw_period}-01")
        if parsed is None:
            # The refusal REUSES `metering.read_batch.period` — the same
            # "reading month" fact the batch tags validate — rather than
            # minting a key in eleven catalogues for one query param (G32
            # zero-baseline ratchet; the read_windows result_unknown borrow
            # set the precedent and the reuse is REPORTED the same way).
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="metering.read_batch.period",
                field_errors=[
                    {
                        "field": "period",
                        "code": errors.VAL_FORMAT,
                        "message_key": "metering.read_batch.period",
                        "params": {},
                    }
                ],
            )
        period_anchor = parsed.date()
    return Response(completeness.chase_list(cycle, period_anchor=period_anchor))


# ── S28 Read import wizard + S25/S29 reads (EP-MET-03/04) ───────────────────
# 11b lists no rows for the reads surface yet, so these paths follow the same
# grammar as the ones above (resource, then verb-as-subpath). REPORTED for the
# A11 addendum rather than invented silently.


class CsvRenderer(BaseRenderer):
    """Passthrough renderer so a CSV-serving view can ANSWER `Accept: text/csv`
    (`DEF-553`): `@api_view`'s default renderers satisfy only JSON, so DRF's
    content negotiation refused the browser's request with 400 BEFORE either
    view ran — S28's template button had never downloaded anything. The views
    return `HttpResponse` and never call `render`; this class exists so the
    negotiation step has a renderer whose media type matches."""

    media_type = "text/csv"
    format = "csv"

    def render(
        self, data: Any, accepted_media_type: Any = None, renderer_context: Any = None
    ) -> Any:
        return data


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([CsvRenderer, JSONRenderer])
def reads_template(request: Any) -> Response:
    """`reads_template.csv` — the PUBLISHED standard template (BR-MET-032).
    One template, downloadable, re-detected on every upload; there is no
    per-tenant variant to serve.

    ⚠ **`?shape=` PICKS WHICH WORKED EXAMPLE — `CR-077`'s reading starters.**
    There is still ONE template: the header row and the mapping are the same
    file for all four, which is what BR-MET-032 means by *"exactly one
    published template"*. What differs is the worked ROWS, because a read
    shape is a file LAYOUT — one row for flat and tiered, three for time of
    use, two for demand (energy + peak) and two for net metering (energy +
    export). `read_import.READ_SHAPES` carries the four and says why seasonal
    is not a fifth.

    ⚠ **NO `shape` STILL SERVES THE EXACT BYTES IT ALWAYS DID**, and that is a
    compatibility promise rather than a default worth defending: this URL has
    handed out the demand pair since CR-038 W4, the spec and the front end
    name `reads_template.csv`, and changing what an unchanged address serves is
    how a bookmark starts lying. Every control on S28 passes a shape, so a
    clerk always chooses.

    ⚠ **AN UNKNOWN SHAPE IS REFUSED BY NAME, NEVER FOLDED TO THE FIRST ONE**
    (`sample_csv`'s posture for an unknown target). The message key is
    `metering.import.kind_unknown` — *"Pick one of: {{allowed}}."* — REUSED
    rather than minted in eleven catalogues for a query parameter, which is the
    reuse `_reading_month` above records two routes down and for the same
    reason.
    """
    require_tenant(request)
    from django.http import HttpResponse

    shape = str(request.query_params.get("shape") or "").strip()
    if not shape:
        filename, body = "reads_template.csv", read_import.template_csv()
    elif shape in read_import.READ_SHAPES:
        filename, body = read_import.starter_csv(shape)
    else:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.import.kind_unknown",
            params={"allowed": ", ".join(read_import.SHAPE_CODES)},
            field_errors=[
                {
                    "field": "shape",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "metering.import.kind_unknown",
                    "params": {"allowed": ", ".join(read_import.SHAPE_CODES)},
                }
            ],
        )
    # CR-161-BRC10 W4 — the utility's own reading fields, one trailing column
    # each; a utility with none is served the published bytes unchanged.
    body = read_import.with_custom_columns(
        body, seams.custom_field_import_columns(services.READ_CUSTOM_ENTITY)
    )
    response = HttpResponse(body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _reading_month(request: Any) -> date:
    """`?period=YYYY-MM` (or a full `YYYY-MM-DD`) → the anchor for the reading
    month, defaulting to the tenant's own today.

    The refusal REUSES `metering.read_batch.period` — the same "reading month"
    fact the batch tags validate — rather than minting a key in eleven
    catalogues for one query param. That is `cycle_chase_list`'s own precedent
    two routes above (G32's zero-baseline ratchet), and the reuse is REPORTED
    here the same way it is reported there.
    """
    raw = str(request.query_params.get("period") or "").strip()
    if not raw:
        return seams.tenant_today()
    parsed = read_import._parse_date(raw) or read_import._parse_date(f"{raw}-01")
    if parsed is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="metering.read_batch.period",
            field_errors=[
                {
                    "field": "period",
                    "code": errors.VAL_FORMAT,
                    "message_key": "metering.read_batch.period",
                    "params": {},
                }
            ],
        )
    return parsed.date()


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # BR-MET-011 — an ops READ, like the chase list
@renderer_classes([CsvRenderer, JSONRenderer])
def cycle_reading_sheet(request: Any, cycle_id: str) -> Response:
    """**CR-054 W1 task 4/5 — `reading_sheet_<cycle>_<month>.csv`.**

    One row per expected meter per required register, with the previous reading
    and its date already in it. This is the file the PO asked for on 2026-08-30:
    *"on step 2 we have ready csv file - with all meters and existing data that
    is availale - only details clark has to fill is readings"*.

    `?period=YYYY-MM` names the reading month; without it, the tenant's current
    month. `?read_method=<code>` writes the stage-1 collection method onto every
    row — omitted, the column is blank and BR-MET-014's batch tag inherits.

    A cycle with no schedule has no window to expect reads in, so there is no
    sheet to serve: it refuses 409, and the refusal REUSES
    `metering.read.reason.cycle_window_not_set` — *"The cycle has no read window,
    so there is nothing to be outside of"* — the catalogue's own sentence for
    exactly this fact, rather than minting an eleventh-catalogue key for it
    (G32's ratchet; `cycle_chase_list`'s reuse precedent). REPORTED: the
    sentence's trailing clause was written for the out-of-window rule and reads
    oddly here; the summary route below states the same absence with no refusal
    at all, and that is the one the download button reads.
    """
    require_tenant(request)
    cycle = selectors.cycle_row(cycle_id)  # tenant-scoped; foreign/unknown = 404
    sheet = reading_sheet.build_reading_sheet(
        cycle,
        period_anchor=_reading_month(request),
        read_method=request.query_params.get("read_method"),
    )
    if sheet.window_absent_reason is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-057",
            message_key="metering.read.reason.cycle_window_not_set",
            params={"reason": sheet.window_absent_reason},
        )
    from django.http import HttpResponse

    response = HttpResponse(
        reading_sheet.reading_sheet_csv(sheet), content_type="text/csv; charset=utf-8"
    )
    filename = reading_sheet.reading_sheet_filename(sheet)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # BR-MET-011 — an ops READ, like the chase list
def cycle_reading_sheet_summary(request: Any, cycle_id: str) -> Response:
    """**CR-054 W1 — what the download button needs to name its own number.**

    RDS-03 stage 2 draws *"↓ Reading sheet for CY-001 · 1,180 rows"* (CR-054
    task 6), and a button that has to download the file to learn its size is a
    button that downloads it twice. Same builder, counted — never a second count
    (hard-won law 5).

    Answers 200 with `window_absent_reason` set when the cycle has no schedule,
    so the button can state the absence without a failed request.
    """
    require_tenant(request)
    cycle = selectors.cycle_row(cycle_id)
    return Response(
        reading_sheet.reading_sheet_summary(
            reading_sheet.build_reading_sheet(
                cycle,
                period_anchor=_reading_month(request),
                read_method=request.query_params.get("read_method"),
            )
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def unit_types(request: Any) -> Response:
    """`GET /units/unit-types` — the tenant's unit-type vocabulary.

    `BR-MET-084` (CR-010 A-4) made unit types a seeded, tenant-extensible
    reference list. **A clerk adds units, so a clerk must be able to read the
    list** — and `/lookups/unit_types` is System-Admin-only, so the Add-units
    wizard could not read it through Settings and fell back to a hardcoded
    five-string array in the bundle instead (`DEF-MET-5656`). This is the same
    door `read_methods` above opened for `DEF-196`, for the same reason.

    READ-ONLY, and the tenant-scoped role gate is the whole authorisation:
    this lists names a clerk must choose between. Writing to the list stays
    where `BR-TEN-036` put it — Settings, System Admin only.
    """
    require_tenant(request)
    return Response({"results": selectors.unit_type_options()})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def read_methods(request: Any) -> Response:
    """`GET /reads/read-methods` - the tenant's read-method vocabulary.

    BR-MET-123 (PO 2026-08-26) makes the read SOURCE a TAG chosen at upload,
    and the words are the tenant's own `read_methods` reference list
    (BR-AST-043). S28 is the Billing Clerk's screen (BR-MET-035) and
    `/lookups/read_methods` is System-Admin-only (DEF-196), so the wizard could
    not read the list through Settings - a clerk would have got an empty
    control, which is the exact shape of the omission the S28 step-1 panel
    already reports about the service tag.

    READ-ONLY, and the tenant-scoped role gate is the whole authorisation: this
    endpoint lists names a clerk must be able to choose between, and writing to
    the list stays where BR-TEN-036 put it - Settings, System Admin only.
    """
    require_tenant(request)
    return Response({"results": selectors.read_method_options()})


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # re-gated in services (BR-MET-035)
def read_batches(request: Any) -> Response:
    """S28 steps 1–2 — stage a batch. Nothing posts (BR-MET-012)."""
    require_tenant(request)
    result = services.stage_read_batch(_actor(request), _payload(request))
    response = Response(result, status=201)
    response["Location"] = tenant_path(request, f"/read-batches/{result['id']}")
    return response


@api_view(["GET", "DELETE"])
@permission_classes([AnyTenantRole])
def read_batch_detail(request: Any, batch_id: str) -> Response:
    require_tenant(request)
    if request.method == "DELETE":
        # BR-MET-054: discard, not destroy — the batch record is retained for
        # audit and simply never appears in Reads.
        return Response(services.discard_read_batch(_actor(request), batch_id))
    batch = services._batch_row(batch_id)
    body = selectors.read_batch_dict(batch)
    body["rows"] = selectors.read_batch_rows(batch, severity=request.query_params.get("severity"))
    # CR-038 W1 (US-MET-018 / BR-MET-057): the review step's cycle coverage —
    # expected meters from the cycle's routes, received in THIS batch,
    # committed before it, and what posting would still leave missing. None
    # WITH its reason for a cycle-less batch (stated absence, never a 0).
    body["cycle_coverage"] = completeness.batch_cycle_coverage(batch)
    if body["cycle_coverage"] is None:
        body["cycle_coverage_absent_reason"] = "batch_not_tagged_with_cycle"
    return Response(body)


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def read_batch_validate(request: Any, batch_id: str) -> Response:
    """S28 step 3 — run the EP-MET-04 engine over every staged row."""
    require_tenant(request)
    return Response(services.validate_read_batch(_actor(request), batch_id))


@api_view(["PATCH"])
@permission_classes([AnyTenantRole])
def read_batch_row(request: Any, batch_id: str, row_no: int) -> Response:
    """S28 step 4 — one row's disposition + reason (BR-MET-015)."""
    require_tenant(request)
    return Response(
        services.set_row_disposition(_actor(request), batch_id, row_no, _payload(request))
    )


@api_view(["PATCH"])
@permission_classes([AnyTenantRole])
def read_batch_row_demand_reset(request: Any, batch_id: str, row_no: int) -> Response:
    """S28 step 4 — BR-MET-051's reset, noted on ONE demand row."""
    require_tenant(request)
    return Response(
        services.set_row_demand_reset(_actor(request), batch_id, row_no, _payload(request))
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def read_batch_demand_reset(request: Any, batch_id: str) -> Response:
    """S28 step 4 — BR-MET-051's reset across the batch's demand rows.

    A technician who resets a fleet of demand registers on one visit says so
    once, about the visit. The answer names every row it wrote and every row it
    skipped, so the clerk who clicked can check it (CLAUDE.md rule 7)."""
    require_tenant(request)
    return Response(services.bulk_demand_reset(_actor(request), batch_id, _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def read_batch_post(request: Any, batch_id: str) -> Response:
    """S28 step 5 — the commit. **PARTIAL SINCE BR-MET-940 (CR-054 task 14).**

    ⚠ **THIS DOCSTRING SAID "the atomic commit" AND THAT IS NOW HALF TRUE, SO
    IT SAYS WHICH HALF.** The TRANSACTION is still atomic — one outer
    `transaction.atomic()`, so a killed process leaves nothing. What is no
    longer all-or-nothing is the FILE: a row the batch cannot file is held with
    a reason and the rest of the readings post, under the PO's *"all or nothing
    will not work - we accept what is correct and rejct what i not correct"*.
    A 1,180-row file with 2 unknown meters answers `posted_reads: 1178`,
    `held_reads: 2` and a link to the file those 2 come back as.

    ⚠ **A SECOND POST OF THE SAME BATCH IS STILL REFUSED** (hard rule 6,
    BR-MET-018) — the batch reaches `posted` whether it filed every row or
    1,178 of them, and the held rows return as a corrected FILE, which is a new
    batch. Nothing here can double-file a reading.

    ⚠ **202 ABOVE THE POST BAR (`DEF-MET-8106`, BR-MET-055).** This read
    *"Synchronous today; the BR-MET-055 async wrapper is REPORTED as
    outstanding"*, and 480 readings then took ~60 s inside a request the web
    worker is killed at. A batch of more than `services.READ_POST_ASYNC_ROW_BAR`
    staged rows now answers **202** with `job_id` + `status_url` (poll
    `GET /jobs/{id}` for `progress`) and `receipt_url`, where the receipt is
    collected once the job has succeeded. At or below the bar: 200 and the
    receipt, exactly as before."""
    require_tenant(request)
    result = services.commit_read_batch(_actor(request), batch_id, _payload(request))
    return Response(result, status=202 if result.get("deferred") else 200)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def read_batch_post_receipt(request: Any, batch_id: str) -> Response:
    """`GET /read-batches/{id}/post-receipt` — what the post did (`DEF-MET-8106`).

    The receipt a background post cannot hand back on the request that started
    it. The batch's own fields are read fresh and the post's figures come from
    `read_import_batches.post_receipt`, written in the post's own transaction —
    the same dict the synchronous post answers with. 404 until the batch has
    posted: a receipt for a post that has not happened is not a receipt."""
    require_tenant(request)
    return Response(selectors.read_batch_post_receipt(services._batch_row(batch_id)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([CsvRenderer, JSONRenderer])
def read_batch_results_csv(request: Any, batch_id: str) -> Response:
    """`GET /read-batches/{id}/results.csv?kind=failures|successes` — **the
    rejects file, and its mirror (CR-054 task 16, BR-MET-941).**

    PO, carried into CR-054: *"we accept what is correct and rejct what i not
    correct - then create csv file at loading stage itself so that suer can see
    all cases thata re rejcted"*.

    ⚠ **ONE PATH AND A `kind` PARAMETER, AND THE WORDS ARE `import_results_csv`'s
    OWN.** They are two representations of one resource — the batch's result —
    and two endpoints would be two places for the refusals and the streaming to
    drift apart (that route's own argument, and `import_sample`'s precedent
    before it). The vocabulary is deliberately the account importer's rather
    than words invented for reads, so a clerk who has run one migration has
    already learned the other.

    ⚠ **`failures` IS AVAILABLE FROM `validated` ONWARD — the PO's *"at loading
    stage itself"*, and `DEF-2487`'s ruling on the same file one importer over:
    the one moment a person most needs the list of what failed is the moment a
    commit has just fallen over, and hanging the download off the receipt screen
    is what made it unreachable there. `successes` needs a post, because before
    the commit nothing has landed and a header with no rows under it reads as an
    ANSWER (`DEF-320`).

    ⚠ **IT STREAMS**, over a generator that reads the batch's rows in chunks:
    `read_import.CSV_ROW_CAP` is 50,000, and a 50,000-row CSV built in memory is
    `DEF-766`'s payload in a download.

    ⚠ **`CsvRenderer` FIRST, FOR `DEF-553`'S REASON** — `@api_view`'s default
    renderers satisfy only JSON, so DRF's content negotiation refuses a
    browser's `Accept` with 400 *before the view runs*. This view returns an
    `HttpResponse` subclass and never calls `render`.

    A READ: it writes nothing, not even an audit row. Downloading the result of
    a batch is not an event (`import_results_csv` takes the same posture).
    """
    tenant_id = require_tenant(request)
    from django.http import StreamingHttpResponse

    batch = services._batch_row(batch_id)  # tenant-scoped; another tenant's = 404
    filename, body = read_rejects.results_csv(batch, request.query_params.get("kind"))
    # ⛔ **`stream_within_tenant_context` IS NOT DECORATION — `DEF-2734`.** The
    # generator above is consumed by WSGI *after* `TenantContextMiddleware` has
    # cleared `app.tenant_id`, so without this its first query runs with no
    # tenant marker, RLS denies on unset, and this route answers 200 with a
    # header and NO ROWS — which a clerk reads as *"nothing was rejected"*.
    # Measured that way on a batch whose screen said "2 rows will not post".
    # The tenant is the REQUEST's, never `batch.tenant_id`; see that function.
    response = StreamingHttpResponse(
        stream_within_tenant_context(tenant_id, body), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def read_batch_cosign(request: Any, batch_id: str) -> Response:
    """S28 — the supervisor CO-SIGN (OQ-042 closure, CR-038 W7 task 5).

    ⛔ The route exists because `cosigned_by` has been SERVED on every batch
    since migration 0003 and **nothing has ever written it** — hard-won law 2,
    and the reason S28's docstring says it draws no co-sign control: *"drawing
    the checkbox would offer a control that changes nothing"*. Now it changes
    something.

    Role is enforced in the SERVICE (`@require_role(SYSTEM_ADMIN, EXECUTIVE)`)
    and not by a route-level class, exactly as every other rule-bearing door in
    this module does it: `AnyTenantRole` lets the request reach the rule, and
    the rule answers with the role refusal a clerk can read.

    ⚠ It does NOT block the post. OQ-042's *"blocks when enabled"* half needs a
    tenant toggle whose home is the S64 settings document another lane owns —
    DEF-815, filed rather than commented."""
    require_tenant(request)
    return Response(services.cosign_read_batch(_actor(request), batch_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def reads(request: Any) -> Response:
    """S25 — server-paginated, 2-year hot window by default (BR-MET-055).
    `archive=true` is the explicit opt-in; no unbounded path exists.

    `f.status=pending` (CR-038 W1 — US-MET-012 §1, verbatim: *"Pending =
    plan-required record (meter × channel, BR-MET-049) with no committed read
    this cycle — derived, not stored"*) serves the DERIVED pending entries —
    expected registers of the open cycle windows with no committed head —
    rather than filtering stored rows, because no stored row exists to filter:
    a `status="pending"` queryset filter would return an empty list that reads
    as "nothing pending". Each entry carries `id: null` and `derived:
    "pending"` so no client mistakes it for an addressable read. Bounded by
    the cycles' own membership (BR-MET-055's posture) and paged like the rest.
    """
    require_tenant(request)
    params = _list_params(
        request, tuple(selectors.READ_SORTS), selectors.READ_DEFAULT_SORT, selectors.READ_FILTERS
    )
    if (params["filters"] or {}).get("status") == "pending":
        entries = completeness.pending_read_entries(filters=params["filters"], q=params["q"])
        return _page(request, entries, lambda row: row)
    rows = selectors.read_result_set(
        q=params["q"],
        filters=params["filters"],
        sort=params["sort"],
        # DEF-044: `dir` was parsed and then dropped on the floor here, so a
        # clicked column header changed the URL and nothing else.
        direction=params["direction"],
        # US-MET-020 TC-3: the opt-in reads the DETACHED (archived) partitions
        # too. Reading only the hot store here would report "no older reads"
        # about reads the retention job had moved, not deleted.
        include_archive=str(request.query_params.get("archive", "")).lower() == "true",
        # MQ-033 (`BR-MET-1218`) — `answer[<question_key>]=<value>`, AND-ed:
        # reads whose field reading answered so. A database subquery, never a
        # list (NFR-3); an unknown shape is ignored (BR-SHL-011).
        answer_filters=read_format_svc.answer_filters(request.query_params),
    )
    return _page(request, rows, selectors.read_dict)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def reads_needs_attention(request: Any) -> Response:
    """S25's landing tab (BR-MET-060). `missing` is the REAL BR-MET-049 count
    since CR-038 W1 (US-MET-018): missing required records — meter × channel —
    across the active cycles whose read window is OPEN (BR-MET-057). This
    docstring said "is not built" and the payload said `missing: null` with a
    reason from W2 until 2026-08-26; both statements retired together with the
    absence they described. `missing_unresolved_meters` rides along so a small
    count over unresolvable meters never reads as "all clear"."""
    require_tenant(request)
    return Response(selectors.needs_attention_counts())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def read_detail(request: Any, read_id: str) -> Response:
    """S29 — the read, its FULL supersession chain and any J6 correction
    linkage opened against it (BR-MET-056 · US-MET-016)."""
    require_tenant(request)
    read = services._read_row(read_id)
    body = selectors.read_dict(read)
    body["chain"] = selectors.read_chain(read_id)
    body["corrections"] = selectors.read_corrections_for_read(read_id)
    # US-AST-011/012 (2026-08-16): the net-metering PAIR. BR-AST-029 stores a
    # solar cycle as TWO records and `validation.py` has enforced that since
    # W2; nothing ever served the two together, so no screen could show them as
    # a pair — which is the whole of that story. Served on the read rather than
    # at its own path because the drawer already fetches this one payload, and
    # a second round trip per open would be a cost with no reader.
    body["net_pair"] = selectors.net_meter_pair(read)
    # `B30` (PO 2026-09-14) — the ACCOUNT, drawn as a live link in ⑪ and served
    # to nobody until today. Resolved here rather than inside `read_dict` for
    # the reason `read_account`'s docstring gives: every other caller of that
    # serializer is a LIST, and one cross-module read per row is the N+1 the
    # batched seam exists to avoid.
    body.update(selectors.read_account(read))
    # MQ-033 (`CR-192-BRC10`, `BR-MET-1218`) — the answers the reader gave to
    # the utility's read format, worded as the stamped VERSION worded them, and
    # any job an answer raised. None for a read that carried no format.
    body["read_format_answers"] = read_format_svc.answers_for_meter_read(read.id)
    # DEF-MET-10633 (FB-003, PO 2026-10-27) — where the reader stood: the
    # position taken at save, or the late one *added at* its own time, and
    # each photograph's. None for a read that did not come from the field.
    body["field_capture"] = field_positions.capture_for_meter_read(read.id)
    return Response(body)


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def read_supersede(request: Any, read_id: str) -> Response:
    """S29 Override = SUPERSEDE (BR-MET-024/053). A billed read is refused —
    its correction routes through J6 (US-MET-016), which billing owns."""
    require_tenant(request)
    result = services.supersede_read(_actor(request), read_id, _payload(request))
    response = Response(result, status=201)
    response["Location"] = tenant_path(request, f"/reads/{result['id']}")
    return response


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def read_billed_correction(request: Any, read_id: str) -> Response:
    """US-MET-016: the J6 route — the ONLY door a BILLED read's correction has.

    Distinct from `/supersede` on purpose. The plain path REFUSES a billed read
    (TC-4) and this one refuses an unbilled one, so neither can be reached by
    accident and the routing is visible in the URL a reviewer reads. The
    response carries the superseding read AND the `read_corrections` linkage
    billing consumes; the invoice itself is untouched (J6 step 1)."""
    require_tenant(request)
    result = services.correct_billed_read(_actor(request), read_id, _payload(request))
    response = Response(result, status=201)
    response["Location"] = tenant_path(request, f"/reads/{result['id']}")
    return response


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # re-gated in services (BR-MET-035)
def read_dispute(request: Any, read_id: str) -> Response:
    """S29 Dispute (US-MET-013 TC-3 · BR-MET-024 · the OQ-043 closure).

    **THE DOOR DEF-046 SAID DID NOT EXIST.** Its first finding, verbatim:
    *"meter_reads carries disputed_at/dispute_reason/disputed_by,
    needs_attention_counts COUNTS disputes, and NO service or route ever sets
    one -- the chip can only ever read zero."* This is that route.

    Records a marker + reason. Changes no value: the correction paths are
    `/supersede` (unbilled) and `/billed-correction` (billed), and neither is
    reachable from here — a dispute is a claim ABOUT a reading, not a change to
    one, and conflating them would let a dispute edit a billed number without
    the J6 linkage BR-MET-053 requires.

    The account is held from the bill run from this moment until a System Admin
    clears it (`/dispute/clear`). Where the read is already BILLED, the response
    carries `billed_bill_effect` = `issued_bill_stands_br_met_133`.

    ⚠ **THIS PARAGRAPH SAID "naming OQ-245 — the issued bill is untouched and
    nothing signs what it should do" UNTIL 2026-08-26.** BR-MET-133 signs it:
    the bill STANDS (it is not voided and not held — hard rule 4), resolution
    goes through the billed-correction door, and while the dispute is open the
    DISPUTED AMOUNT does not age into late fees while the undisputed remainder
    ages normally.
    """
    require_tenant(request)
    return Response(services.dispute_read(_actor(request), read_id, _payload(request)))


@api_view(["POST"])
# OQ-043's closure names the role: "hold account from run until SysAdmin
# clears". Gated here AND in the service (BR-SHL-025 defence in depth).
@permission_classes([SystemAdminOnly])
def read_dispute_clear(request: Any, read_id: str) -> Response:
    """Clear the dispute and release the account back into the bill run.

    System Admin only, by the OQ-043 closure. An optional `resolution` note
    rides into the audit row — `meter_reads` has no cleared-reason column (B2
    r8) and inventing one is a story's job.
    """
    require_tenant(request)
    payload = request.data if isinstance(request.data, dict) else {}
    return Response(services.clear_read_dispute(_actor(request), read_id, payload))


@api_view(["DELETE"])
@permission_classes([AnyTenantRole])
def read_batch_row_delete(request: Any, batch_id: str, row_id: str) -> Response:
    """BR-MET-054's delete scope, and the ONLY delete verb in this module's
    reads surface: a staged/rejected row of an un-posted batch. There is no
    endpoint that deletes a committed read, by design (US-MET-016 TC-5/TC-6)."""
    require_tenant(request)
    return Response(services.delete_staged_read_row(_actor(request), row_id))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def reads_estimate(request: Any) -> Response:
    """Estimate ONE missing (meter, channel) record (BR-MET-026/058/062). A
    refusal comes back as data with its reason — "no history — field visit" is
    an answer the clerk must see, not a 500."""
    require_tenant(request)
    return Response(services.estimate_missing_read(_actor(request), _payload(request)))


# ── CR-023 · the RECORDED import runner, stages 1–3 (B15 §12 rows 1–4) ──────
#
# ⚠ **THESE SUPERSEDE `POST /premises/imports` + `/commit` ABOVE, AND BOTH ARE
# STILL MOUNTED ON PURPOSE.** Design B15 §7A: the stateless pair is called
# today by `AddPremisesWizard`'s bulk path and by PRM-07 step 1, so deleting it
# before the recorded path has a screen would remove a working feature. The
# honest order is stated there and is the order being followed — build the
# recorded path, move the wizard's bulk choice onto it (BR-MET-093 already
# rules that the unit wizard's bulk mode IS the runner, and the same applies
# here), then retire the stateless pair in ONE commit that says what it retires.
# **Do not leave both indefinitely:** two import paths into `premises` is the
# shape that gives a customer two different answers about what happened to
# their file.
#
# ⚠ **ONLY ONE STAGE EVER WRITES A PREMISES, AND IT IS `POST
# /imports/{id}/load` — the last route in this block.** Stages 1–3 write run
# rows and nothing else (B15 §16 TC-1), `/dry-run` computes the same figures
# the loader will act on and writes NOTHING, `/receipt` is a read, and
# `/rollback` deactivates rather than deletes (hard rule 4). Every docstring
# below says which half it is in, because that is the one property of this
# workflow a reader has to be able to check without running it.
logger = logging.getLogger(__name__)

#: The reference the browser minted for this request (`client.ts newRequestRef`).
#: Eight hex characters grouped in the middle, because a person reads it aloud.
SUPPORT_REF_HEADER = "HTTP_X_SUPPORT_REF"
_SUPPORT_REF = re.compile(r"^[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}$")


def _support_ref(request: Any) -> str:
    """The caller's own reference, or `-` when it sent none.

    ⚠ **VALIDATED TO A SHAPE, AND THAT IS NOT CEREMONY.** It is written into a
    log line, so an unvalidated header is a log-injection hole: a newline in it
    forges a second line. The shape is the one `newRequestRef` mints and the
    one `supportRef` renders, and anything else is discarded rather than
    trimmed — a half-read reference is worse than none because support would
    look it up and find nothing.
    """
    value = str(request.META.get(SUPPORT_REF_HEADER) or "").strip()
    return value.upper() if _SUPPORT_REF.match(value) else "-"


def _trace_import_stage(request: Any, stage: str, **facts: Any) -> Any:
    """⛔ **`DEF-965` / `DEF-1080` — THE LINE THAT MAKES THE NEXT REPORT
    DIAGNOSABLE, WRITTEN BEFORE ANY WORK.**

    Two Product Owner reports of one production failure, and neither could be
    diagnosed from this repo: the refusal on screen said *"Something went
    wrong. Nothing was saved — try again."* and carried nothing anybody could
    quote back. The mechanism turned out to be `DEF-1075`, a **gunicorn worker
    timeout** — so there was no exception, no envelope and no `trace_id`,
    because Django never got to form a response at all.

    ⚠ **WHICH IS WHY THIS LOGS ON ARRIVAL RATHER THAN ON THE WAY OUT.** A line
    written after the work is a line a killed worker never writes. This one is
    already in the container log when the sixty seconds run out, and it names
    the same reference the operator is reading off their screen.

    `logger.info` reaches the console handler under `DEBUG=False` — the `apps`
    logger is configured for it (settings/base.py `LOGGING`, added for
    `DEF-1076`), which is the whole reason a log line is worth writing here.

    Returns the monotonic start, so the caller can close the pair with an
    elapsed figure — the number that would have named `DEF-1075` on sight.
    """
    logger.info(
        "import stage=%s ref=%s tenant=%s %s",
        stage,
        _support_ref(request),
        core_tenancy.current_tenant_id(),
        " ".join(f"{key}={value}" for key, value in facts.items()),
    )
    return time.monotonic()


def _trace_import_done(request: Any, stage: str, started: Any, **facts: Any) -> None:
    """The other half of the pair. A stage with an opening line and no closing
    one IS the finding: it is a request that never came back."""
    logger.info(
        "import stage=%s ref=%s done elapsed_ms=%d %s",
        stage,
        _support_ref(request),
        int((time.monotonic() - started) * 1000),
        " ".join(f"{key}={value}" for key, value in facts.items()),
    )


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def imports(request: Any) -> Response:
    """`POST` — stage 1 · EXTRACT: file received, hashed SERVER-SIDE, every row
    staged. NOTHING is written to `premises` (BR-MET-085 · B15 §4.1).

    `GET` — PRM-04's run table, newest first. A READ; it writes nothing, not
    even an audit row, because looking at a list is not an event.
    """
    require_tenant(request)
    if request.method == "GET":
        return Response(import_runs.run_list(request.query_params))
    started = _trace_import_stage(request, "extract")
    staged = import_runs.extract(_actor(request), _payload(request))
    _trace_import_done(request, "extract", started, run=staged.get("id"))
    return Response(staged, status=201)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([CsvRenderer, JSONRenderer])
def import_sample(request: Any) -> Response:
    """`CR-025` — the sample CSV stage 1 offers for download. A READ that
    writes nothing: header row derived from `target_columns` (BR-MET-088),
    one example row (the `reads_template.csv` precedent, BR-MET-032).

    ⛔ **AND, ON THE SAME URL, WHAT ITS COLUMNS TAKE (`DEF-1077`).** Ask for
    `application/json` and this answers the template's NOTES instead of the
    file: the columns that declare a `help` sentence, plus any `blank_reason`
    this tenant's own data makes true. One resource, two representations —
    the notes are ABOUT the sample, so they live at the sample's own address
    rather than at a second endpoint that could drift from it.

    ⚠ **CSV IS STILL THE DEFAULT FOR ANYTHING BROWSER-SHAPED**, which is what
    `DEF-553` fixed: a browser sends `Accept: */*` and negotiation lands on
    `CsvRenderer`, first in the list. Only an explicit JSON `Accept` — which is
    what `ApiClient` sends unless a caller names another type — takes the notes
    branch, so the download button is untouched (it asks for `text/csv`).
    """
    require_tenant(request)
    from django.http import HttpResponse

    target = str(request.query_params.get("target") or "").strip()
    if getattr(request.accepted_renderer, "format", "csv") == "json":
        return Response(import_runs.sample_notes(target))
    filename, body = import_runs.sample_csv(target)
    response = HttpResponse(body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def import_columns(request: Any, run_id: Any) -> Response:
    """Stage 2's `MAPS TO` list — **the REAL target columns** (BR-MET-088) plus
    this tenant's own custom fields, plus `— ignore —`, plus the transforms we
    cannot offer and why."""
    require_tenant(request)
    run = import_runs.read_run(run_id, with_rules=False)
    return Response(
        {
            "target": run["target"],
            "columns": import_runs.target_columns(run["target"]),
            "unavailable_transforms": list(import_runs.UNAVAILABLE_TRANSFORMS),
            "row_handling": list(import_runs.ROW_HANDLING_KEYS),
        }
    )


def _stage_response(result: dict[str, Any]) -> Response:
    """200, or **202 when the stage went to a worker** (CR-026).

    B12 r1 §3: every async operation answers 202 with a job id and where to
    poll. The engine decides WHICH — a file over `import_runs.ASYNC_ROW_BAR`
    comes back `deferred: true` with the job id already in the payload — so the
    status code follows the engine rather than the API layer forming its own
    opinion about how big is big. Every answer, deferred or not, carries the
    run and its `progress`, so one screen renders both cases.
    """
    return Response(result, status=202 if result.get("deferred") else 200)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def import_run_detail(request: Any, run_id: Any) -> Response:
    """**THE POLL SURFACE (CR-026).** One run, its counts, its rules and its
    live `progress` — *"Validating… 62,000 of 100,000"*.

    A READ. It writes nothing, not even an audit row, because a screen asking
    *"how far?"* every two seconds is not an event; that is also why it must
    stay cheap enough to be asked that often.

    ⚠ **`?reject_offset=` / `?reject_limit=` — THE REJECT WINDOW (DEF-766).**
    "Cheap enough to be asked that often" was a claim this route did not keep:
    the reject list rode along unbounded and each reject carries its full source
    cells, so the PO's 9,881-reject run answered 4.28 MB every two seconds. The
    window defaults to the screen's own first page and is clamped in
    `import_runs.reject_window`; the payload states the TOTAL beside it, so the
    operator still reads *"9,881"* and the pager still reaches every one of
    them — one page per request instead of all of them per poll.
    """
    require_tenant(request)
    return Response(
        import_runs.read_run(
            run_id,
            reject_offset=request.query_params.get("reject_offset"),
            reject_limit=request.query_params.get("reject_limit"),
        )
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def import_transform(request: Any, run_id: Any) -> Response:
    """Stage 2 · TRANSFORM — in / duplicates dropped / forward. NO WRITE.

    **202 over `ASYNC_ROW_BAR` rows** — measured at 77.9s for 50,000, which no
    browser waits for; poll `GET /imports/{id}` (or the job's own URL) for the
    gauge. Under the bar, unchanged: 200, with the answer.
    """
    require_tenant(request)
    started = _trace_import_stage(request, "transform", run=run_id)
    result = _stage_response(import_runs.transform(_actor(request), run_id, _payload(request)))
    _trace_import_done(request, "transform", started, run=run_id, status=result.status_code)
    return result


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def import_save_mapping(request: Any, run_id: Any) -> Response:
    """Stage 2's "Save mapping as template" (BR-AST-048 — COPY-ON-WRITE: a new
    tenant row in tenancy's `import_mappings`, never an update of a system
    default). Writes ONE tenancy row through the seam; no run row moves."""
    require_tenant(request)
    return Response(
        import_runs.save_mapping_template(_actor(request), run_id, _payload(request)),
        status=201,
    )


@api_view(["PATCH"])
@permission_classes([AnyTenantRole])
def import_row_fix(request: Any, run_id: Any, row_no: int) -> Response:
    """r10's inline correction — *"Fix the rejects here — no need to
    re-upload"* — patch ONE staged row's raw cells by source-column name
    (CR-028: *"Load into inventory instead"* is this route clearing
    `UNIT_REF`). Writes RUN ROWS ONLY, never a target row, and sends the run
    back to stage 1 so stages 2–3 re-judge before anything can commit. The
    `read_batch_row` PATCH is the shape's precedent."""
    require_tenant(request)
    return Response(import_runs.fix_row(_actor(request), run_id, row_no, _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def import_validate(request: Any, run_id: Any) -> Response:
    """Stage 3 · VALIDATE — checked / clean / errors / warnings, the rules AS
    THEY WERE (BR-MET-090) and the reject list. NO WRITE.

    **202 over `ASYNC_ROW_BAR` rows** (50.8s measured at 50,000), as transform.
    """
    require_tenant(request)
    # ⛔ **CR-046 wave B — THE WRITE MODE REACHES STAGE 3.** Optional, and its
    # absence is NOT `insert`: the run keeps whatever it recorded at stage 1
    # (possibly nothing), and a rule that rejects rows never fires on a mode
    # nobody stated. The body carries it for the same reason `/dry-run` does —
    # it is the operator's choice about a write, not a property of the URL.
    mode = str(_payload(request).get("write_mode") or "").strip() or None
    started = _trace_import_stage(request, "validate", run=run_id, mode=mode)
    result = _stage_response(import_runs.validate(_actor(request), run_id, mode))
    _trace_import_done(request, "validate", started, run=run_id, status=result.status_code)
    return result


# ── CR-023 · stages 4 and 5 (B15 §12 rows 5–9) ──────────────────────────────
#
# ⚠ **ONE OF THESE FOUR WRITES AND THREE DO NOT, AND THE SPLIT IS THE WHOLE
# SAFETY PROPERTY OF THE DESIGN.** r10 prints it under its own title — *"Five
# stages · nothing is written until you commit at stage four"* — so a reader
# must be able to tell which route breaks that promise without running it.
# `/dry-run` rehearses, `/receipt` reads, `/rollback` DEACTIVATES (never
# deletes, hard rule 4), and `/load` is the only one that creates a row.
#
# ⚠ **`/dry-run` AND `/load` SHARE ONE PREDICATE ON PURPOSE.** `_load_locked`
# calls `import_runs.dry_run` itself and acts on the figures it returns, so the
# sentence the operator reads and the rows the commit touches cannot disagree
# (B15 §16 TC-16: *"a dry run that lies is worse than none"*). Nothing here
# recomputes a figure the engine already answers.


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def import_dry_run(request: Any, run_id: Any) -> Response:
    """Stage 4's REHEARSAL — what a commit in this write mode would do. **NO
    WRITE**, not even an audit row.

    Serves `will_create` / `will_update` / `rejected` / `unplanned_units`, the
    `approval` block (BR-MET-098's two bars beside the run's own numbers) and,
    for `replace` only, BR-MET-099's three numbers — `not_in_file`,
    `skipped_occupied`, `will_deactivate`. The write mode is a BODY field
    rather than a query param because it is the operator's choice about a
    write, and re-running it is how the screen answers *"what changes if I pick
    a different mode"*.
    """
    require_tenant(request)
    payload = _payload(request)
    mode = str(payload.get("write_mode") or "insert").strip()
    started = _trace_import_stage(request, "dry_run", run=run_id, mode=mode)
    figures = import_runs.dry_run(_actor(request), run_id, mode)
    _trace_import_done(request, "dry_run", started, run=run_id)
    return Response(figures)


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # re-gated in the service (BR-MET-035)
def import_confirm_changeover(request: Any, run_id: Any) -> Response:
    """**POST the opening balances a run is HOLDING, under the operator's real
    changeover date** (PO ruling 2026-08-27).

    An accounts import that ran without a changeover date loaded every account
    and posted **no journal entry at all** — which is the only state in which
    the date is still changeable, because hard rule 4 makes a posted entry
    permanent. This is the door that ends that state, and it is the only one.

    `{"changeover_on": "2026-07-31"}` — *the last day your old system was in
    charge of the money*. That sentence is the label the screen must use: the
    Product Owner met the word *cutover* on a screen that blocks people and
    could not tell what it was for, and nobody at a two-person utility will do
    better.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        import_runs.confirm_changeover_date(
            _actor(request), run_id, payload.get("changeover_on")
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # re-gated in the service (BR-MET-035)
def import_load(request: Any, run_id: Any) -> Response:
    """Stage 4 · LOAD — **THE ONLY ROUTE IN THIS WORKFLOW THAT WRITES.**

    Creates and updates rows of the run's target, retires what a `replace` run
    no longer carries (BR-MET-099 — DEACTIVATE, never DELETE), records a
    rollback point, and answers with stage 5's receipt. A second commit of the
    same run returns that same receipt rather than loading twice (hard rule 6).

    ⚠ **CR-026 — OVER `ASYNC_ROW_BAR` ROWS THIS ANSWERS 202 AND THE COMMIT RUNS
    IN A WORKER** (101.5s measured at 50,000 rows, in ONE transaction: the load
    is all-or-nothing and the decision log of 2026-08-22 records why). Three
    answers are still given on THIS call and never by poll, because each is a
    refusal or a receipt the caller asked for: an already-loaded run returns its
    receipt (hard rule 6), a run that never validated is refused, and BR-MET-098's
    approval bar is checked before anything is enqueued.

    ⚠ **BR-MET-098's APPROVER IS CHECKED HERE — AND, SINCE `DEF-545`, IN THE
    ENGINE TOO.** The rule reads *"THE APPROVER IS AN OWNER OR AN ADMIN … the
    same pair of roles as the rate-change second approval (BR-RAT-091's 10%
    bar)"*, and this product's answer to that pair is `SystemAdminOnly` — which
    is exactly what `/discounts/{id}/versions/{vid}/approve` already carries.
    The clerk keeps the LOAD (that is `AdminOrClerk` above and
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` in the service); what they may
    not do is be the second pair of eyes.

    ⚠ **THIS SENTENCE SAID "HERE, AND HERE ONLY" UNTIL 2026-08-27, AND IT ENDED
    "REPORTED rather than fixed at source".** Both halves are now false and
    that is the point: `import_runs._load_locked` carries its own `BR-MET-098`
    refusal, so a service-layer caller — a management command, a worker, the
    next module — no longer walks past the only check there was (`BR-SHL-025`,
    defence in depth). **The two layers are deliberately not identical.** This
    one refuses `approved` from a non-admin ALWAYS, because at the edge a flag
    a caller may not set is worth refusing on sight. The engine's fires only
    where the bar is actually crossed, because that is where the rule speaks.
    Do not "align" them by loosening this one.
    """
    require_tenant(request)
    payload = _payload(request)
    if bool(payload.get("approved")) and getattr(request, "tenant_role", None) != SYSTEM_ADMIN:
        raise errors.BizError(
            errors.BIZ_APPROVAL,
            br_ref="BR-MET-098",
            message_key="metering.import.approver_role",
        )
    # `DEF-965` — the arrival line, before the write. See `_trace_import_stage`.
    started = _trace_import_stage(request, "load", run=run_id, mode=payload.get("write_mode"))
    result = _stage_response(import_runs.load(_actor(request), run_id, payload))
    _trace_import_done(request, "load", started, run=run_id, status=result.status_code)
    return result


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([CsvRenderer, JSONRenderer])
def import_results_csv(request: Any, run_id: Any) -> Response:
    """`GET /imports/{run_id}/results.csv?kind=successes|failures` — **the two
    files a migration comes out as (CR-047 task 13).**

    PO ruling 2026-08-29, verbatim: *"at the end we need 2 CsV file 1 for
    success record and other for failed records"*.

    ⚠ **THE FAILURES FILE IS THE OPERATOR'S OWN FILE PLUS TWO COLUMNS**
    (`why_it_failed`, `how_to_fix_it`) — same headers, same order, same cells.
    They fix two things in the spreadsheet they already know and upload it
    again; a file under OUR column names would have to be re-mapped first.

    ⚠ **IT STREAMS.** `StreamingHttpResponse` over a generator that reads the
    run's rows from the database in chunks, because the file sizes the PO named
    for this runner are *"50,000 or 100,000 … at a time"* and a 100,000-row CSV
    built in memory is DEF-766's 4.28 MB payload twenty times over. Nothing
    larger than one row exists at once.

    ⚠ **`CsvRenderer` FIRST, FOR `DEF-553`'S REASON.** `@api_view`'s default
    renderers satisfy only JSON, so DRF's content negotiation refused a
    browser's `Accept` with 400 *before the view ran* and the S28 template
    button had never downloaded anything. This view returns an
    `HttpResponse` subclass and never calls `render`; the renderer exists so
    negotiation has a media type that matches.

    A READ: it writes nothing, not even an audit row — downloading the receipt
    of a run is not an event (`imports`' own GET takes the same posture).
    """
    tenant_id = require_tenant(request)
    from django.http import StreamingHttpResponse

    filename, body = import_runs.results_csv(run_id, request.query_params.get("kind"))
    # ⛔ **`stream_within_tenant_context` IS NOT DECORATION — `DEF-2734`.** Same
    # trap as `read_batch_results_csv` one route over, and it bit this file
    # HARDER: `_failures_csv` calls `_source_headers(run)` inside the generator,
    # and that function's pre-`DEF-2513` FALLBACK is a query — so on a run whose
    # column order has to be re-derived from its rows (which is every run on the
    # shared development database) the operator's own nine columns were denied
    # along with the rows and the file came back as `why_it_failed,how_to_fix_it`
    # with nothing under it. A run that stored its order keeps its header and
    # still loses every row.
    response = StreamingHttpResponse(
        stream_within_tenant_context(tenant_id, body), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def import_receipt(request: Any, run_id: Any) -> Response:
    """Stage 5 · RESULT — the receipt, READ from what the run recorded.

    ⚠ Nothing on this path counts a row again (BR-MET-090's posture applied
    past the commit): a receipt reading *"245 loaded"* in August must still
    read it in December, whatever anyone has deactivated since.

    ⚠ **`import_runs._run` IS REACHED FOR DELIBERATELY AND IT IS REPORTED.**
    `receipt()` takes the run MODEL and the module publishes no
    `read_receipt(run_id)`. The alternative was an ORM query in this file,
    which B8/LAW 0 forbids outright; `_run` is a tenant-scoped read inside the
    SAME app that raises `NotFoundError` for a run of another tenant, so the
    module boundary is intact and only the underscore is wrong. A public
    `read_receipt` belongs in `import_runs.py`, which this lane does not own,
    and is REPORTED in the build report rather than reached into twice.

    ⚠ **AND TODAY THIS ROUTE REFUSES EVERY RUN THAT HAS A RECEIPT (`DEF-541`).**
    `_run()` rejects the statuses `loaded` and `rolled_back` before `receipt()`
    is reached — one guard that also kills the load's idempotency branch and
    the rollback entirely. The route is mounted rather than withheld because it
    is CORRECT: when that guard learns to take its allowed statuses from its
    caller, this answers without a line changing here. The screen does not
    depend on it — stage 5 draws the receipt `/load` already answered with.
    """
    require_tenant(request)
    return Response(import_runs.receipt(import_runs._run(run_id)))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # re-gated in the service (BR-MET-035)
def import_rollback(request: Any, run_id: Any) -> Response:
    """Reverse what a run created — and it **DEACTIVATES; IT DOES NOT DELETE**
    (hard rule 4), skipping anything now occupied and reporting how many.

    Answers the same receipt shape stage 5 draws, with the run now
    `rolled_back` and its rollback point spent, so one screen renders both.
    """
    require_tenant(request)
    return Response(import_runs.rollback(_actor(request), run_id))


# ── S21 Usage tab · BR-MET-106 (CR-030 W3 task 3.8) ────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a read of rows GET /accounts/{id} already implies
def account_usage(request: Any, account_id: str) -> Response:
    """`GET /accounts/{id}/usage` — the ACC-01 Usage tab's chart and KPI strip.

    ⚠ **MOUNTED FROM `metering`, NOT FROM `customers`, AND THE PATH IS STILL
    `/accounts/…`.** `meter_read_monthly_usage` is metering's table (BR-MET-106
    is a metering rule and the figure is Σ over `meter_reads`), so the module
    that owns the data serves it; the URL names the RESOURCE a clerk is looking
    at, which is an account. `apps/customers/api.py` lists the
    `/accounts/{id}/…` subpaths it deliberately does not serve and `usage` is
    not among them, so nothing is being taken from another module.

    NO 11b ROW TO FOLLOW — the usage surface has no contract entry, like the
    eleven `/reads` routes and the nine `/imports` routes before it. House
    grammar (resource, then subpath); REPORTED for the A11 addendum with them.

    `?months=` accepts r10's own filter vocabulary (12 or 24) and FALLS BACK to
    24 for anything else rather than 4xx-ing (BR-SHL-011).

    **It does not recompute.** A GET that writes is a GET that surprises
    somebody; `monthly_usage_service.recompute_account` is the writer and is
    called by the lane that changes reads. An account whose months have never
    been computed therefore serves an empty `series` and every month ABSENT,
    which is the truthful answer to *"what has been stated about this
    account?"* — see the frontend's own stated absence.
    """
    require_tenant(request)
    try:
        months = int(request.query_params.get("months", ""))
    except (TypeError, ValueError):
        months = monthly_usage_reads.DEFAULT_WINDOW_MONTHS
    return Response(
        monthly_usage_reads.usage_payload(account_id, months=months, include_reads=True)
    )


# ── S50 usage strip · CR-038 W5 task 8, the METER half of BR-MET-106 ────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a read of rows GET /assets/{id} already implies
def asset_usage(request: Any, asset_id: str) -> Response:
    """`GET /assets/{id}/usage` — the trailing-12-month strip, PER REGISTER.

    PO verbatim, 2026-08-26: *"We ahve to calcualet last 12 month consumption
    from these readings and display it on account and meters"*. The account
    half is `/accounts/{id}/usage` above; this is the meter half CR-038's
    ADDITION section measured as the gap.

    ⚠ **THE TWO ENDPOINTS ARE NOT THE SAME QUERY WITH A DIFFERENT KEY, AND THE
    PAYLOAD SAYS SO.** The account one reads the STORED `monthly_usage` rows;
    that table is keyed (account, service, month) and has no asset or channel
    grain, so it cannot answer for one meter — let alone for one register of a
    TOU meter, whose windows BR-MET-135/BR-RAT-014 forbid blending. This one
    computes from the meter's own committed reads through the SAME
    `monthly_usage` rules module, and publishes `source:
    "computed_from_reads"` plus `stored_source_absent` naming **OQ-421** so a
    reader comparing two figures knows which is which. See
    `apps/metering/asset_usage.py` for the whole disposition.

    `?months=` takes 12 or 24 and FALLS BACK to 12 rather than 4xx-ing
    (BR-SHL-011) — 12 because that is the PO's own word for this task.

    Mounted from `metering` on an `/assets/…` path for the same reason
    `/accounts/{id}/usage` is: the module that owns `meter_reads` owns the
    figure, and the URL names the resource the clerk is looking at. No 11b row
    to follow; REPORTED for the A11 addendum with the others.
    """
    require_tenant(request)
    try:
        months = int(request.query_params.get("months", ""))
    except (TypeError, ValueError):
        months = asset_usage_reads.DEFAULT_WINDOW_MONTHS
    return Response(asset_usage_reads.asset_usage_payload(asset_id, months=months))


# ── CR-038 W5 task 7 · bulk operations on the reads list ───────────────────
@api_view(["POST"])
@permission_classes([AnyTenantRole])  # re-gated in services (BR-MET-035)
def reads_bulk_fix(request: Any) -> Response:
    """`POST /reads/bulk-fix` — accept a SET of flagged reads, ONE reason.

    PO verbatim, 2026-08-26: *"We will need bulk operation"*, and on the
    accountability half: *"keep the rule — speed comes from the bulk button…
    an auditor asking 'who chose to estimate M-4412?' gets a name"*. Every row
    this writes carries `fixed_by`, `fix_reason` and its own `audit_log` row —
    there is no anonymous bulk statement anywhere behind this route.

    **BR-MET-129 bounds what it can do:** a warned reading already POSTED and
    stays posted. This records a judgment after commit (clause 3); it neither
    posts a reading nor holds one out, and no error is ever cleared by it —
    an error still refuses at import (BR-MET-015's surviving half).

    A partly-refused selection answers **200 with per-row outcomes**, not a
    4xx: thirty-eight accepted and two explained is the honest result of the
    click, and failing all forty over two would be worse for the clerk and
    less true.
    """
    require_tenant(request)
    return Response(services.bulk_fix_reads(_actor(request), _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # re-gated in services (BR-MET-035)
def reads_bulk_estimate(request: Any) -> Response:
    """`POST /reads/bulk-estimate` — estimate a SET of missing records.

    Every target goes through `estimate_missing_read`, so BR-MET-026's
    arithmetic, BR-MET-027's two-consecutive limit and BR-MET-058's per-channel
    history are the SAME code the single-row door runs. **A bulk button is a
    different surface, never a different pipeline.**

    A refusal the rules make — *"no history — field visit"* — comes back as a
    named row beside the estimates, never as a silent skip.
    """
    require_tenant(request)
    return Response(services.bulk_estimate_reads(_actor(request), _payload(request)))


# ── CR-038 W5 task 6 · the quick single-reading entry (S28's counter case) ──
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def reads_quick_context(request: Any) -> Response:
    """`GET /reads/quick-context` — what the quick-entry MODAL must know first.

    PO verbatim, 2026-08-26: *"we will need modpage to load single reading, if
    it is simple then modal"*. A modal is sanctioned *if it is simple*, and
    **whether this meter is simple is a question only the server can answer** —
    it depends on the plan-driven expected register set (BR-MET-049), which
    lives in `completeness.PlanRegisterResolver`.

    So this read answers three things, and the modal cannot be honest without
    any of them:

      1. **The meter**, resolved by number or id within this tenant, with its
         own UoM (hard rule 3 — the modal shows the unit, never guesses it).
      2. **Its registers.** One expected channel → the modal is the right
         surface. Several (a TOU or demand meter) → `simple: false` and the
         modal HANDS OFF to the full manual entry path rather than growing rows
         inside itself. That is the *"if it is simple"* boundary, applied per
         meter, exactly as CR-038's task 6 words it.
      3. **The cycle and period the read will land in** — DERIVED from the read
         date and the meter's own cycle assignment, per CR-038's period/cycle
         sanity statement clause 4: *"the quick single-read modal DERIVES cycle
         + period from the read date and the meter's cycle assignment and SHOWS
         them (the clerk confirms, never types)"*.

    ⚠ **IT WRITES NOTHING.** A GET that stages a batch is a GET that surprises
    somebody. The reading is staged, validated and posted by the SAME three
    `/read-batches` routes a CSV uses — this route only tells the modal what to
    draw before the clerk commits.
    """
    require_tenant(request)
    return Response(
        quick_read.quick_entry_context(
            meter_no=request.query_params.get("meter_no"),
            asset_id=request.query_params.get("asset_id"),
            read_at=request.query_params.get("read_at"),
        )
    )


# ── CR-030 W5 · the move-in wizard's two unit reads (B18 §5.5.5) ────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a read of what GET /units/{id} already implies
def unit_assets(request: Any, unit_id: str) -> Response:
    """`GET /units/{id}/assets` — B18 W5 task 5.2, move-in step 3's asset panel.

    *"Every meter, sub-meter and behind-the-meter device at the unit"*, grouped
    on `asset_types.category` **post-CR-028** (BR-AST-004: exactly one tab per
    asset) and NOT on the `(sub)/(master)` qualifier — a behind-the-meter
    inverter hangs off its meter by `parent_asset`, so the qualifier would file
    it as a sub-meter. See `selectors.unit_assets` for the whole disposition.

    NOT PAGED, and deliberately: this is everything installed at ONE unit, the
    panel draws all of it at once, and a `{count, next}` envelope would describe
    navigation no control offers (the `route_read_windows` reasoning, same
    grammar). An unknown or foreign unit id is 404 through `unit_row`, before
    any asset is read — never an empty panel that would read as *"nothing is
    installed here"*.

    NO 11b ROW TO FOLLOW — B18 §5.5.5 marks this endpoint **NEW**. House
    grammar (resource, then subpath), REPORTED for the A11 addendum with the
    `/reads` and `/imports` routes that are in the same position.
    """
    require_tenant(request)
    return Response(selectors.unit_assets(unit_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a read of what GET /units/{id} already implies
def unit_account(request: Any, unit_id: str) -> Response:
    """`GET /units/{id}/account` — CR-089 wave I, the S15 Account tab.

    `DEF-CUS-4691`: the tab rendered FIVE facts — number, status, start, balance,
    autopay — and every one of them was correct. What it could not show was that
    the account carries a medical certificate, so **a supervisor standing on the
    unit arranging a shut-off could not see the one row that forbids it.**

    NOT PAGED, for `unit_assets`' reason one route up: this is everything about
    ONE account at ONE unit, the tab draws all of it at once, and a `{count,
    next}` envelope would describe navigation no control offers. The one list
    inside it — the account's notes — is the account's whole set, ordered pinned-
    first by the index customers built for it.

    An unknown or foreign unit is a 404 through `selectors.unit_row`, before any
    account is read.
    """
    require_tenant(request)
    return Response(unit_account_reads.unit_account(unit_id))


def _pricing_period(request: Any) -> tuple[date | None, date | None]:
    """`?period_start=&period_end=` — BOTH or NEITHER, and never half of one.

    CR-034 (b). A caller that names one end and not the other has asked a
    question with no answer: `as_of` is the period END (BR-RAT-007) and a start
    with no end names no service date at all. Silently defaulting the missing
    half would answer a DIFFERENT question than the one asked and print the
    result under the caller's own heading, so it refuses by name instead.

    ABSENT is a legitimate, first-class answer — see `selectors.unit_pricing`:
    no period is invented, `as_of` becomes the tenant's today, and the response
    says which of the two it did.

    `date.fromisoformat` and nothing looser, for `billing/api._date_field`'s
    reason: a date parsed by guessing at a format resolves a different rate
    version in one region than in another.
    """
    raw_start = request.query_params.get("period_start")
    raw_end = request.query_params.get("period_end")
    # A cleared date input arrives as "" and means *nobody typed one*, exactly
    # as `billing/api._optional_date_field` reads it.
    raw_start = raw_start.strip() if isinstance(raw_start, str) else raw_start
    raw_end = raw_end.strip() if isinstance(raw_end, str) else raw_end
    if not raw_start and not raw_end:
        return None, None
    if not raw_start or not raw_end:
        # ⚠ EXISTING CATALOGUE KEYS, AND THE REUSE IS DELIBERATE (G32). Every
        # `message_key` the backend raises must resolve to a customer sentence,
        # and that gate is a RATCHET AT ZERO with no register — so a lane that
        # cannot write catalogue copy must not mint a key either, or the refusal
        # goes SILENT (DEF-322: "a path that looks handled and communicates
        # nothing"). `metering.lookups.required` says *This is required*, and
        # the FIELD ERROR beside it names which box, which is what the screen
        # renders under the input.
        #
        # ⚠ THREE MORE PRECISE SENTENCES ARE OWED and are handed over rather
        # than invented here — see the lane report. When they land, these three
        # raises take them and nothing else changes.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="metering.lookups.required",
            field_errors=[
                {
                    "field": "period_start" if not raw_start else "period_end",
                    "code": errors.VAL_REQUIRED,
                }
            ],
        )
    parsed: list[date] = []
    for name, raw in (("period_start", raw_start), ("period_end", raw_end)):
        try:
            parsed.append(date.fromisoformat(str(raw)))
        except (TypeError, ValueError) as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                # *"Enter the date as YYYY-MM-DD."* — metering's own key, the
                # exact sentence, already in every catalogue.
                message_key="metering.cycle.bad_date",
                field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
            ) from problem
    start, end = parsed
    if end < start:
        # A reversed window is not a narrow one — it has no days at all, and
        # `as_of` would then sit BEFORE the period it claims to price.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            # *"The period ends before it begins."* — the same fact billing's
            # run refuses, so the customer sentence is the same sentence. The
            # NAMESPACE is billing's and this is metering, which is a smell:
            # if billing renames its key this refusal goes silent, which is the
            # failure G32 exists to prevent. A metering-namespaced twin is owed
            # and is REPORTED, not minted (the repo already carries two such
            # twins — `ledger.report.range_inverted` and
            # `reports.viewer.range_inverted` — so the pattern is established).
            message_key="billing.run.error.periodOrder",
            field_errors=[{"field": "period_end", "code": errors.VAL_RANGE}],
        )
    return start, end


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def unit_pricing(request: Any, unit_id: str) -> Response:
    """`GET /units/{id}/pricing` — B18 W5 task 5.3 + **CR-034 (b)**, the unit's
    Plan tab: what this unit is priced on FOR A STATED PERIOD.

    🔒 Serves rating's figures; computes none of them. The period and its
    `as_of` · plan (and the plan CHANGES inside the period, reported never
    collapsed) · services and their base charges · one rate-schedule card per
    service WITH its blocks, resolved on the service date · minimum charges ·
    charge codes WITH the code's own amount · discounts the plan OFFERS ·
    taxes · the penalty rule.

    `?period_start=&period_end=` are optional and are BOTH-or-NEITHER. **With
    neither, the answer is byte-identical to what this endpoint served before
    CR-034 (b)** — `period: null`, `as_of` = the tenant's today. No default
    month is invented; `selectors.unit_pricing` carries the calendar worked
    example for why that would show a customer next month's rates.

    **The worked month B18 asks for is still NOT served and the payload states
    its own absence** (OQ-363) — nothing in this product prices a plan outside a
    bill run, and no signed rule says what consumption a worked month would be
    priced at. Inventing either would be billing math this repo has frozen
    (B4/B5, GT-1..61) or an open question resolved by picking a value.

    Four further absences are STATED rather than filled, each with its own
    reason so no screen renders one sentence for several facts: a unit with no
    plan · a plan this tenant cannot read · rating not publishing at all · the
    discount GRANT and the CONTRACT, neither of which a unit can answer.
    """
    require_tenant(request)
    period_start, period_end = _pricing_period(request)
    return Response(
        selectors.unit_pricing(unit_id, period_start=period_start, period_end=period_end)
    )


# ── S86 · NCT-01 the New Connect worklist (CR-030 W6 task 6.12) ─────────────
#: What this list CANNOT do, served on every response so the screen disables the
#: four tabs it cannot fill and says WHY, instead of rendering tabs that 500 or
#: — worse — tabs that quietly show the wrong builds.
#:
#: G28/CR-016: `detail` is what a utility user reads and carries no ids, no
#: routes and no rule codes; `br_ref` is the machine field that keeps the
#: provenance reachable for us. G38's discipline pointed at a server payload:
#: `tracks` names the row whose closure kills this sentence, so the absence
#: expires by itself instead of outliving the question.
CONNECTIONS_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "segments_not_decided",
        "br_ref": "OQ-371 (OPEN) · B18 §5.4.2 · §5.4.9 NCT-01",
        "tracks": "OQ-371",
        "segments": list(connection_reads.SEGMENTS_DRAWN_BUT_UNSERVED),
        "detail": (
            "Every new connect is listed together for now. The In progress, Waiting, "
            "Partly activated and Done tabs are switched off because a build can be "
            "part-way through AND waiting on somebody at the same time, and which of "
            "those two tabs should hold it has not been decided yet. Filtering them "
            "on a guess would hide a build rather than show it in the wrong place."
        ),
    },
)


def _connections_envelope(request: Any, result: dict[str, Any], segment: str) -> dict[str, Any]:
    """The SAME four envelope keys `StandardPagination` emits — `count` /
    `next` / `previous` / `results` — built by hand because the SELECTOR did the
    slicing.

    ⚠ **ONE SHAPE.** Every list in this product answers the DRF envelope
    unconditionally (see `_asked_for_a_page`'s removal note above: eight shipped
    call sites once read two of these endpoints as bare arrays). A worklist that
    answered `{"rows": …}` because its selector happened to paginate would be a
    second contract for the same idea, and the frontend's list plumbing would
    need a special case for one screen.

    **Why the selector paginates at all** is in `connection_reads`'s §4: each
    row costs three derivation queries through `connections.py`, so paging must
    happen BEFORE the rows are built, and `StandardPagination` can only slice a
    list that already exists. `kpis` rides alongside exactly as REQ-01's strip
    does in `service_request_api._paginated`.
    """
    per, page, total = result["per"], result["page"], result["total"]
    last = max(1, -(-total // per))
    url = request.build_absolute_uri()
    return {
        "count": total,
        "next": replace_query_param(url, "page", page + 1) if page < last else None,
        "previous": replace_query_param(url, "page", page - 1) if page > 1 else None,
        "results": result["rows"],
        "kpis": result["kpis"],
        "segment": segment,
        "unavailable": list(CONNECTIONS_UNAVAILABLE),
        # ⚠ **THESE FIVE KEYS WERE COMPUTED AND THEN DROPPED ON THE FLOOR FROM
        # 2026-08-27 UNTIL TODAY, AND THAT IS WHY THE NEW CONNECTS TAB HAD NO
        # FILTER CONTROL AT ALL (`DEF-CUS-5432`).** `list_connections` has
        # returned `filters`, `states`, `sorts`, `sort` and `dir` since CR-045
        # wave D; this envelope listed the keys it forwards by hand and was
        # never amended, so the screen received a payload with no `states` on
        # it. `offerableFilters` then correctly dropped a group with no options,
        # `FilterBar` correctly returned `null` for a screen declaring none, and
        # the toolbar correctly rendered nothing — every layer behaving exactly
        # as written, over a capability the clerk could not reach.
        #
        # **Nothing could see it.** `ConnectionList` DECLARES both fields, so
        # `tsc` is satisfied by the type rather than by the server; the frontend
        # cases build their own payload WITH `states` in it, so they prove the
        # fixture; and the backend cases call `list_connections` directly, below
        # this function, so they prove the selector. The only check that could
        # have caught it is one that reads what the ROUTE answers, which is what
        # `test_w6_connection_list` now does.
        #
        # Forwarded by NAME rather than by spreading `result`, deliberately:
        # `rows`, `page`, `per` and `total` are this envelope's own business and
        # are already re-expressed above as `results`/`count`/`next`/`previous`.
        "filters": result["filters"],
        "states": result["states"],
        "sorts": result["sorts"],
        "sort": result["sort"],
        "dir": result["dir"],
    }


@api_view(["GET", "POST"])
@permission_classes([ConnectionsReadAnyWriteAdminOrClerk])  # read: all three · write: A4
def connections(request: Any) -> Response:
    """`GET /connections` — B18 §5.4.6's list row, and S86's only endpoint.
    **`POST /connections` — `create_connection`, CR-070 wave B (`US-WRK-002`).**

    ⚠ **THE POST IS SERVED FROM THIS FUNCTION AND NOT FROM ITS OWN VIEW, AND
    THAT IS A ROUTING FACT RATHER THAN A PREFERENCE.** Django reaches only the
    FIRST view registered on a path, so a sibling `path("connections", …)` for
    the write would be dead code that looked mounted — the exact bug `G52`
    found in the lane that built the refunds doors. One path, one view, and the
    role split lives in the permission class where it can be cited.

    ⚠ **THE POST IS NOT THE WIZARD'S COMMIT DOOR AND MUST NOT BECOME ONE.**
    `NewConnectWizard.tsx` posts to `POST /connections/commit` with NO id,
    because `BR-MET-112` means no connection row exists before step 9. That door
    is still unserved and is REPORTED where it always was
    (`newConnectEndpoints.ts` exception E3). This mounts the finished writer so
    that no writer in `connections.py` is behind a Python shell (`US-WRK-002`
    TC-7), and so a draft can be raised against an existing premises.

    The read half was read-only until CR-070 wave B, when the twelve other write
    paths this module holds got their doors; the reason given here for the
    absence — *"they belong to the wizard's lane"* — outlived the absence by
    nine days, which is hard-won law 1 in one comment.

    ⛔ **`?segment=` accepts `all` and nothing else** — `NotImplementedError(
    "OQ-371")` otherwise, the posture `finance/cost-reconciliation/download`
    already takes for OQ-204: a named refusal rather than a 404, because a 404
    reads as a typo and this is a decision nobody has taken. The screen is told
    the same thing in words it can render, on `unavailable`, so it never has to
    call the route to find out.

    `q`/`page`/`per` are parsed by the ONE house parser (BR-SHL-011); `sort` and
    `dir` are declared empty because B18 §5.4.2 fixes the order — *"Sorted by
    target date, soonest first"* — and an undeclared param is ignored, never
    refused.
    """
    require_tenant(request)
    if request.method == "POST":
        # THIN. `create_connection` allocates the `CON-` number, may create the
        # premises it builds on (`BR-MET-1024`), writes its own audit row and
        # derives the state. Nothing is added here.
        return Response(w6_connections.create_connection(_actor(request), _payload(request)))
    # CR-045 wave D task D.11 (DEF-1702) — `f.state` joins the declared
    # vocabulary. `allowed_sorts` stays EMPTY: §5.4.2 fixes the order and an
    # undeclared param is ignored, never refused.
    params = parse_list_params(
        request.query_params,
        # `BR-CUS-1046` / `DEF-CUS-5060` — this list declared NO sorts and
        # fixed one `.order_by(...)`, so *newest first* would have replaced the
        # only ordering a clerk had rather than being a default they could
        # override. `OQ-CUS-1790` measured that on six lists and the PO chose
        # option (c): *"All eight open newest-first and the six gain a sort
        # control."*
        allowed_sorts=tuple(connection_reads.SORTS),
        default_sort=connection_reads.DEFAULT_SORT,
        default_dir=connection_reads.DEFAULT_DIR,
        allowed_filters=connection_reads.CONNECTION_FILTERS,
    )
    segment = str(request.query_params.get("segment") or connection_reads.SEGMENT_ALL)
    #: ⚠ **THE REFUSAL IS A SENTENCE, NOT A 500 (2026-08-25).** This handler let
    #: `NotImplementedError("OQ-371")` escape, so an unserved segment reached the
    #: caller as a **server error** — while its sibling `GET /disconnects`
    #: translated the identical refusal into a readable catalogue message. Two
    #: worklists, one unruled question, two different experiences: on one screen
    #: the product looks broken and on the other it explains itself.
    #:
    #: Found by the story lane reading both endpoints side by side to write
    #: their acceptance criteria — which is the argument for writing the story
    #: even when the code is already built. → **DEF-698**.
    #:
    #: Neither screen can reach it today (both disable the tabs client-side),
    #: which is exactly why it went unnoticed: an API contract nothing calls is
    #: still an API contract.
    try:
        result = connection_reads.list_connections(
            segment=segment,
            q=params.q or None,
            page=params.page,
            per=params.per,
            filters=params.filters,
            sort=params.sort,
            dir=params.dir,
        )
    except NotImplementedError as unruled:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="metering.connections.segment_unavailable",
            params={"segment": segment, "supported": connection_reads.SEGMENT_ALL},
        ) from unruled
    return Response(_connections_envelope(request, result, segment))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 gives Executive VIEW on this family
def connection_detail(request: Any, connection_id: Any) -> Response:
    """`GET /connections/{id}` — S88 `NCT-02`, the connection detail.

    ⚠ **THE SCREEN HAS BEEN LIVE AND BROKEN, WHICH IS WHY THIS VIEW IS ONE
    LINE.** `ConnectionDetailPage.tsx` is built, is routed at
    `/connections/:connectionId`, and rendered the server's own 404 because the
    read behind it did not exist — hard-won law 2 with the halves the other way
    round: wired, and not built.

    **It computes nothing.** No figure is derived here, no absence is defaulted
    and no null is filled: the read model's payload is returned verbatim,
    `unavailable` included, so the four fields the product cannot produce reach
    the screen as nulls beside the reasons the service wrote for them. A view
    that helpfully turned one of them into `0` would be DEF-127 again.

    `AnyTenantRole`, matching `connections` above and NOT the `AdminOrClerk` the
    write doors beside it carry. The asymmetry is deliberate: A4 gives Executive
    VIEW on this family, and reading a build is not committing one.
    """
    require_tenant(request)
    return Response(connection_reads.connection_detail(connection_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ, like `connection_detail` above
def connection_build_record(request: Any, connection_id: Any) -> Response:
    """`GET /connections/{id}/record` — **the whole build record, in one call.**

    Everything blueprint pages 98–107 draw: the header, the five tiles, the six
    `Overview` blocks and the first page of every list the six drawn tabs carry.

    ⚠ **THIS SERVES THE PROPERTY'S BUILD TAB AND DOES NOT REVIVE A BUILD
    SCREEN.** `OQ-MET-12520` closed 2026-09-21 on the PO's option C — *"The
    drawing isn't asking for a duplicate; it's asking for completeness we don't
    have"* — which re-confirms the 2026-09-04 ruling that deleted
    `ConnectionDetailPage.tsx` and adds what the blueprint was really asking
    for: the drawn tabs land on the Build tab AS SECTIONS. Pages 100–107 stay
    the CONTENT contract; their address and tab strip are superseded.
    `/connections/:id` still REDIRECTS on the client and nothing here changes
    that.

    ⚠ **ONE CALL, BECAUSE THE POINT OF THE RULING IS THAT THE CLERK STOPS
    HOPPING BETWEEN THREE PLACES.** Three round trips to fill one tab would be
    that problem wearing a different hat, so every list comes back on page one
    and `?section=` pages one of them deeper. `?page` / `?per` follow
    `BR-SHL-011` — clamp, never error — and every list carries its own
    `count`/`page`/`per` (`NFR-3`: no unpaginated list anywhere).

    **It computes nothing.** The read model's payload is returned verbatim,
    `unavailable` included, so every figure the product cannot produce reaches
    the screen as a null beside the reason the service wrote for it. A view that
    helpfully turned one into `0` would be `DEF-127` again — and on the
    `OUTSTANDING` tile a zero says *settled* about a debt.

    `AnyTenantRole`, matching the detail read above and NOT the `AdminOrClerk`
    the write doors carry: A4 gives Executive VIEW on this family, and reading a
    build is not committing one.
    """
    require_tenant(request)
    params = request.query_params
    return Response(
        connection_record.build_record(
            connection_id,
            section=params.get("section") or None,
            page=params.get("page") or 1,
            per=params.get("per"),
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ, like `connections` and the detail above
def connection_message_templates(request: Any) -> Response:
    """`GET /connections/message-templates` — **step 7's drawn picker rows.**

    ⚠ **BOTH HALVES WERE BUILT AND NEITHER WAS REACHABLE (hard-won law 2).**
    `connection_messages.template_choices` and
    `notifications.connection_events.connection_templates` landed on 2026-09-16
    with thirteen green cases between them, and `connection_events.py`'s own
    lifecycle block records the gap in as many words — *"D=deferred(reached
    through metering's seam, no HTTP surface of its own)"*. The step-7 screen is
    the wave that needs it, so the address is mounted here rather than the
    picker shipping over an empty table.

    ⚠ **NO CONNECTION ID, AND THAT IS `BR-MET-112` RATHER THAN AN OVERSIGHT.**
    Step 7 runs seven steps before anything is written, so there is no build to
    hang this read on. It lists the three classes for the TENANT; which of them
    a given build can actually queue is `queue_on_commit`'s answer and is not
    knowable here.

    ⚠ **THE LITERAL IS REGISTERED ABOVE `connections/<uuid:connection_id>`** —
    the same house habit as `connections/commit` below it, for the same reason.

    **THIN.** The search term is passed through untouched: `template_choices`
    matches *the name a human gave it* (B14 rule 31) and this view neither
    filters nor sorts, so a clerk and a test see one behaviour.
    """
    require_tenant(request)
    typed = (request.query_params.get("search") or "").strip()
    return Response(connection_messages.template_choices(search=typed or None))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # the clerk on step 6; it writes NOTHING
def connection_quote_preview(request: Any) -> Response:
    """`POST /connections/quote-preview` — **what this build will cost, before it exists.**

    ⚠ **THIS ADDRESS EXISTS BECAUSE A MONEY SCREEN SHOWED NO MONEY
    (`DEF-CUS-6115`).** New Connect step 6 counted its quantities, named the
    charge code a clerk picked, and printed no unit price, no line total and no
    total — so the acceptance walk committed six builds without the clerk ever
    seeing a figure, and the commit then raised `7 x $45.00 = $315.00`. The
    pricing engine could always answer; this is the door that asks it.

    ⚠ **A POST THAT WRITES NOTHING, AND THE PRECEDENT IS BILLING'S OWN.**
    `POST /billing/one-time/preview` is the same shape for the same reason: the
    question is a LIST of coded lines and a list does not fit in a query string.
    Nothing here creates a run, a document or a number.

    ⚠ **NO CONNECTION ID, AND THAT IS `BR-MET-112` RATHER THAN AN OVERSIGHT** —
    the same sentence `connection_message_templates` above it carries. Step 6
    runs two steps before anything is written, so there is no build to hang this
    on. The whole payload is the question.

    ⚠ **THE LITERAL IS REGISTERED ABOVE `connections/<uuid:connection_id>`**,
    the house habit this file already keeps for `connections/commit`.

    **THIN.** `connection_reads.preview_quote` reads the lines through the
    commit's own shape check and prices them through the commit's own engine;
    this view computes no figure and defaults no absence.
    """
    require_tenant(request)
    return Response(connection_reads.preview_quote(_payload(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # same right as the commit below — it IS a commit
def connection_commit_new(request: Any) -> Response:
    """`POST /connections/commit` — **the New Connect wizard's one press.**

    ⚠ **THIS ADDRESS ANSWERED 404 UNTIL 2026-09-16 AND THE BUTTON HAS BEEN
    PRESSING IT SINCE THE WIZARD SHIPPED (`DEF-MET-5441`).** `NewConnectWizard`
    posts here with NO id in the path, because `BR-MET-112` means no connection
    row exists before the last step. Wave B mounted the thirteen connection
    writers and deliberately did not mount this one — `create_connection` needs
    a premises and `commit_connection` needs an existing draft — and the
    orchestration behind one door was left unwritten, recorded in two comments
    and on no register. **No build made through that screen had ever reached the
    database.**

    ⚠ **THE LITERAL IS REGISTERED ABOVE `connections/<uuid:connection_id>/…`,
    AND THAT IS THE HOUSE HABIT RATHER THAN A FIX.** `<uuid:…>` would not match
    `commit` today, so nothing is currently at risk; the ordering is what stops
    the next literal being swallowed the day somebody registers a looser
    converter beside it.

    **THIN, like every other view here.** The whole payload IS the plan — the
    id-bearing commit below reads `request.data["plan"]` because a lane wrapped
    it, and this screen sends the plan itself — and `commit_new_connect`
    sequences the two services inside one transaction. This view computes no
    figure and defaults no absence.
    """
    require_tenant(request)
    return Response(w6_connections.commit_new_connect(_actor(request), _payload(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # a commit writes across five modules — not a VIEW right
def connection_commit(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/commit` — S87 step 9's ONE commit (task 6.10).

    ⚠ **THIS IS THE ONLY DOOR THE WIZARD POSTS TO, AND THAT IS THE POINT.**
    `BR-MET-112` says *"nothing is written until step 9"*, so the whole wizard
    is a draft. Three sequential POSTs from a browser would invent exactly the
    half-committed state the rule forbids — a premises created, then the tab
    closed, and a unit that belongs to nothing. The orchestration therefore
    lives in `connections.commit_connection`, which sequences five modules'
    own services rather than writing across them (CLAUDE.md's cross-module
    ban), and this view sequences nothing at all.

    It computes no figure and defaults no absence: the seven-count manifest it
    returns is the service's, verbatim.
    """
    require_tenant(request)
    plan = request.data.get("plan")
    return Response(w6_connections.commit_connection(_actor(request), connection_id, plan))


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # the FIELD reports; the human act below is gated harder
def work_order_field_result(request: Any, work_order_id: Any) -> Response:
    """`POST /work-orders/{id}/field-result` — BR-MET-110 step one.

    PO 2026-08-25: *"Work order will send the data and confirm from field;
    utility staff will review these work order, accept them and use data from
    them to activate these services."*

    **Nothing activates here.** This deliberately does the least: it records
    what the field sent. The act that matters is `/accept` below, and keeping
    them two doors is what makes the review a real review rather than a
    formality the transport performs on staff's behalf.
    """
    require_tenant(request)
    return Response(
        w6_connections.submit_field_result(
            _actor(request),
            work_order_id,
            field_data=request.data.get("field_data"),
            outcome=request.data.get("outcome"),
            external_ref=request.data.get("external_ref"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-MET-110's human act — never AnyTenantRole
def work_order_accept(request: Any, work_order_id: Any) -> Response:
    """`POST /work-orders/{id}/accept` — BR-MET-110 step two, THE HUMAN ACT.

    ⚠ **THIS ROUTE IS WHY THE COMMIT ABOVE IT MATTERS: BR-MET-110 AND
    BR-MET-115 WERE RULED, BUILT, TESTED AND AUDITED WITH NO WAY FOR A HUMAN
    TO PERFORM THE ACT.** `connections.dispatch_communication`'s own docstring
    read *"NO SUCH BUTTON IS DRAWN ANYWHERE"* — a signed trigger reachable only
    from a Python shell. S88's work-order drawer now carries the control and
    this is the door behind it.

    One human act, one auditable moment, three consequences (PO 2026-08-25):
    data accepted, service activated, customer told. **The third is guarded,
    not defaulted — `OQ-372`**: the PO fixed the TRIGGER and did not say which
    job's completion sends the letter, so the service refuses rather than
    picking one, and this view passes that refusal through unchanged.
    """
    require_tenant(request)
    return Response(w6_connections.accept_field_result(_actor(request), work_order_id))


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE B · THE FOURTEEN FINISHED WRITERS GET A DOOR (US-WRK-002)
# ══════════════════════════════════════════════════════════════════════════
# `US-WRK-002` §5 names FOURTEEN finished writers and the wave is named for
# them. Thirteen live in `connections.py`: TWELVE are mounted below and the
# thirteenth, `create_connection`, is the POST half of the `connections` view
# above (one path, one view — see its docstring). The fourteenth is
# `create_work_order`, mounted from `apps/work/api.py` as `POST /work-orders`,
# because Work owns the raise every door uses (`07-endpoints.md` §1 row 14).
# The two READERS — `outstanding_work()` and `characteristic()` — ride inside
# `GET /connections/{id}` and get no route of their own.
#
# ⚠ **THE PLAN'S OWN CELL SAYS "ELEVEN CONNECTION ACTS" AND THEN LISTS TWELVE**
# (`10-execution-plan.md` §3 wave B, task B1). `07-endpoints.md` §1's header is
# the count that survives measurement — *"The fourteen writers mounted, and the
# queue — 15"* — and it agrees with `US-WRK-002` §5's table of fourteen names
# and with TC-7's guard. Built to fourteen; the miscount is corrected in the
# plan and recorded in the decision log rather than resolved by silently
# building whichever number was convenient.
#
# ⚠ **EVERY VIEW HERE IS THIN, AND THAT IS THE WHOLE STORY.** `CR-070` §11 task
# 0.2: *"Read them before rewriting them; they are written and tested."* Not one
# refusal, default, derivation or audit row is authored here — each function
# already writes its own (hard rule 7), already refuses a cancelled build, and
# already re-derives the connection state through `refresh_connection_state`.
# A view that "helpfully" filled a null or re-checked a state would be a second,
# drifting copy of a rule that is already signed and tested.
#
# ⚠ **`AdminOrClerk`, NOT `AnyTenantRole` — AND THE ASYMMETRY IS THE RULE.**
# A4 gives the Executive VIEW on this family (*"view across operational
# modules"*), so the two READS above admit all three roles and every WRITE here
# admits System Admin and Billing Clerk only. `BR-SHL-025`: the server refuses
# regardless of what the button looked like — `US-WRK-002` TC-3, proved with an
# Executive rather than with the Billing Clerk the story names, because this
# product has exactly three roles and A4 gives the Clerk *"full on
# Premises/Accounts"*. The rule TC-3 asserts is unchanged; only the actor who
# can demonstrate it is (decision log 2026-09-04).
#
# ⚠ **NO NEW REFUSAL SENTENCE IS WRITTEN BY THIS WAVE.** Every refusal these
# doors can produce is one the service already raises against a catalogue key
# that already resolves (`metering.connection_already_stamped`,
# `metering.connection_cancelled`, `metering.connection_service_transition_
# refused`, `metering.todo.title_required`, `work.order.anchor_required` …), so
# G32's unresolved count stays 0 and G33's six-word cap is not owed a new line.


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_add_service(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/services` — `add_connection_service`, step 4.

    One service, at one unit or at the premise. The service refuses a service
    the tenant does not run through metering's own seam, so the refusal is the
    same sentence the unit wizard gives.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        w6_connections.add_connection_service(
            _actor(request),
            connection_id,
            service_code=payload.get("service"),
            unit_id=payload.get("unit_id"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_service_transition(
    request: Any, connection_id: Any, connection_service_id: Any
) -> Response:
    """`POST /connections/{id}/services/{sid}/transition` — `transition_service`.

    The connection id is in the path for the shape of the resource and is NOT
    re-checked here: the service filters the row by the tenant in context and
    answers a stranger's id with the same 404 an absent row gets (`BR-TEN-003`).
    Re-deriving the parent link in the view would be a second copy of a check
    the service already makes correctly.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        w6_connections.transition_service(
            _actor(request),
            connection_service_id,
            payload.get("to_state"),
            reason=payload.get("reason"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_submit(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/submit` — `submit_connection`: Draft → Requested."""
    require_tenant(request)
    return Response(w6_connections.submit_connection(_actor(request), connection_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_hold(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/hold` — `hold_connection`, with the REASON.

    The reason is required by the service, not defaulted here: *"Left off,
    because the permit has not come back"* is the thing the hold exists to
    carry, and an unattributed hold is half a hold.
    """
    require_tenant(request)
    return Response(
        w6_connections.hold_connection(
            _actor(request), connection_id, reason=_payload(request).get("reason")
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_release(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/release` — `release_connection`.

    `waiting_on` is PASSED, never assumed: a build can come off hold and still
    be waiting for materials, which is exactly what `CON-26-0121` draws. The
    caller says; neither the service nor this view guesses.
    """
    require_tenant(request)
    return Response(
        w6_connections.release_connection(
            _actor(request), connection_id, waiting_on=_payload(request).get("waiting_on")
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_cancel(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/cancel` — `cancel_connection`, with the reason.

    The destructive one, and the only door on this screen wearing B14 rule 6's
    danger tier. Nothing here is irreversible in the database — the stamp is a
    timestamp — but the derived state becomes `cancelled` and every other door
    on this build then refuses (`_refuse_if_cancelled`).
    """
    require_tenant(request)
    return Response(
        w6_connections.cancel_connection(
            _actor(request), connection_id, reason=_payload(request).get("reason")
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_waiting_on(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/waiting-on` — `set_waiting_on`, on a build that is
    NOT held. Waiting on something and being on hold are two independent axes
    (`NCT-01` fact 1a), which is why this is its own door and not a flag on the
    hold."""
    require_tenant(request)
    return Response(
        w6_connections.set_waiting_on(
            _actor(request), connection_id, waiting_on=_payload(request).get("waiting_on")
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_mark_outstanding(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/outstanding-work` — `mark_outstanding` (BR-MET-114).

    ⚠ **THE SERVICE IS `mark_outstanding`, NOT `mark_outstanding_work`.**
    `07-endpoints.md` §1 rows 9–10 and the wave plan both name the longer
    spelling; the code has carried the shorter one since CR-030 W6. Recorded
    here rather than renamed, because renaming a signed, tested service to match
    a table cell is the tail wagging the dog (the docs are corrected instead).
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        w6_connections.mark_outstanding(
            _actor(request),
            connection_id,
            title=payload.get("title"),
            detail=payload.get("detail"),
            # `CR-162-BRC10` — `kind: "note"` adds a note to the To-do tab.
            kind=payload.get("kind"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_close_outstanding(request: Any, connection_id: Any, todo_id: Any) -> Response:
    """`POST /connections/{id}/outstanding-work/{tid}/close` — `close_outstanding`.

    **Only a PERSON closes one** — the service refuses without a resolvable
    `identity.User` behind the actor, by name (`BR-MET-114`), and this view does
    not soften that into a default.
    """
    require_tenant(request)
    return Response(w6_connections.close_outstanding(_actor(request), todo_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_owner_account(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/owner-account` — `create_owner_account` (BR-MET-116).

    A CROSS-MODULE write that goes through customers' own `create_master_account`
    seam; a build with no common-area unit is refused by name rather than given
    an invented anchor.
    """
    require_tenant(request)
    return Response(
        w6_connections.create_owner_account(_actor(request), connection_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_add_fee(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/fees` — a fee added after submission (`CR-163-BRC10`
    item 2). A NEW issued bill against the build's payer, never an edit of the
    quote (hard rule 4); `connection_fees.add_connection_fee` holds the rule.
    `AdminOrClerk`: raising a receivable is a write."""
    require_tenant(request)
    from apps.metering import connection_fees

    return Response(
        connection_fees.add_connection_fee(_actor(request), connection_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_message_send(request: Any, connection_id: Any, code: str) -> Response:
    """`POST /connections/{id}/messages/{code}/send` — *Send now* / *Resend*.

    `CR-163-BRC10` item 26. Body `{channel, recipient}`; `channel` is one of
    email · pdf_print · sms and `recipient` is `owner` or `co_applicant`. One
    letter, one channel, the next copy — `connection_messages.send_now` holds
    the whole rule, and `notifications.queue_document` is the only write.
    `AdminOrClerk`: sending is a write a read-only role may not make.
    """
    require_tenant(request)
    payload = _payload(request)
    connection = w6_connections._connection_or_404(connection_id)
    return Response(
        connection_messages.send_now(
            _actor(request),
            connection,
            code,
            channel=str(payload.get("channel") or ""),
            recipient=str(payload.get("recipient") or connection_messages.RECIPIENT_OWNER),
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def connection_message_preview(request: Any, connection_id: Any, code: str) -> Response:
    """`GET /connections/{id}/messages/{code}/preview` — what the letter would
    say for THIS build. A READ: nothing is queued and no number is spent."""
    require_tenant(request)
    connection = w6_connections._connection_or_404(connection_id)
    return Response(connection_messages.preview(connection, code))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_tag_charges(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/charges/tag` — `tag_charges_to_account` (BR-MET-113).

    It refuses to RE-tag: a quote that moved debtor after being stated is the
    hazard hard rule 4 exists for, and a correction is a new charge on the right
    account rather than a quiet re-pointing of the old one.
    """
    require_tenant(request)
    return Response(
        w6_connections.tag_charges_to_account(
            _actor(request), connection_id, _payload(request).get("account_id")
        )
    )


@api_view(["PUT"])
@permission_classes([AdminOrClerk])
def connection_unit_characteristic(
    request: Any, connection_id: Any, unit_id: Any, key: str
) -> Response:
    """`PUT /connections/{id}/units/{uid}/characteristics/{key}` — `set_characteristic`.

    `PUT` and not `POST` because the key is in the path and the write is
    idempotent on it: the same key set twice is one row with the second value.

    ⚠ **`unit_of_measure` IS REQUIRED AND IS NOT DEFAULTED HERE** — hard rule 3,
    and the reason `BR-MET-108` refused a column per service. A view that
    supplied a unit when the caller left it out would be inventing the one fact
    the rule exists to make explicit.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        w6_connections.set_characteristic(
            _actor(request),
            unit_id,
            service_code=payload.get("service"),
            key=key,
            value=payload.get("value"),
            unit_of_measure=payload.get("unit_of_measure"),
        )
    )


# ── S64 · Read validation & estimation rules (CR-038 A1) ────────────────────
# Registered from METERING because metering owns both stores (B2 r16 #6 called
# `read_validation_settings` metering-owned; `settings_families.py`'s own
# docstring reserved "re-homing is a one-migration move when the metering lane
# wants it" — CR-038 A1 is that moment). The URL is unchanged for the client:
# tenancy's route is REMOVED in the same commit, so `/settings/read-validation`
# resolves here instead of to the tenant_settings jsonb document the engine
# never read (the divergence CR-038 A1 exists to close — "take it from there").
@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def read_validation_settings(request: Any) -> Response:
    """`GET /settings/read-validation` — the whole S64 picture (general panel +
    one entry per enabled service + the locked integrity vocabulary).
    `PUT` saves the tenant-wide estimation panel. A4 grants Settings "Full" to
    System Admin and "View" to Executive, so the class admits both and the
    SERVICE's @require_role refuses the Executive's write with 403 AUTH-002
    (BR-SHL-025 defense in depth)."""
    require_tenant(request)
    if request.method == "PUT":
        return Response(services.save_read_validation_general(_actor(request), _payload(request)))
    return Response(selectors.read_validation_overview())


@api_view(["PUT"])
@permission_classes([AdminOrExecutive])
def read_validation_service_settings(request: Any, service: str) -> Response:
    """`PUT /settings/read-validation/{service}` — one enabled service's VEE
    thresholds (CR-038 A1) **and its per-rule ENABLED switches** (BR-MET-136).
    Partial change set in, the saved row out; a service with no row yet
    requires every FIGURE (no ratified figure exists to merge with —
    BR-MET-020) but never the switch map, whose default IS ratified: all
    enabled. Every successful write appends ONE audit row naming field, old,
    new and actor, plus a second `settings.read_validation.rule_switched` row
    when a switch moved.

    `rule_enabled` is `{rule: bool}` and is MERGED over what is stored — naming
    one rule never re-enables the others. An attempt to disable an INTEGRITY
    rule is REFUSED 422 with the rule NAMED (BR-MET-136 clause 4), never
    ignored: a save that silently drops the request would leave an admin
    believing they turned off a check that is still running."""
    require_tenant(request)
    return Response(
        services.save_read_validation_service(_actor(request), service, _payload(request))
    )


# ── CR-162-BRC10 · approve / activate, the To-do tab, Add unit ───────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])  # a READ, like `connection_detail`
def connection_activation(request: Any, connection_id: Any) -> Response:
    """`GET /connections/{id}/activation` — every unit × service row of the
    build, what stands on it, its orders, whether it is ready, and what the
    Approve warning will list (`connection_activation.activation_readiness`)."""
    require_tenant(request)
    from apps.metering import connection_activation

    return Response(connection_activation.activation_readiness(connection_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_activate(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/activate` — `{service_ids, acknowledge_open_orders}`.

    One transaction per press: the service rows activate through
    `transition_service`, their assets install, the premises and the owner's
    master account become Active on the first one, and the messages go
    (`connection_activation.activate`). Refusals name the unit and the order."""
    require_tenant(request)
    from apps.metering import connection_activation

    payload = _payload(request)
    return Response(
        connection_activation.activate(
            _actor(request),
            connection_id,
            service_ids=payload.get("service_ids"),
            acknowledge_open_orders=bool(payload.get("acknowledge_open_orders")),
        )
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def connection_todos(request: Any, connection_id: Any) -> Response:
    """`GET /connections/{id}/todos` — the To-do tab: to-dos and notes, newest
    first (`connections.todo_list`)."""
    require_tenant(request)
    return Response(w6_connections.todo_list(connection_id, viewer=_actor(request)))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_reopen_outstanding(request: Any, connection_id: Any, todo_id: Any) -> Response:
    """`POST /connections/{id}/outstanding-work/{tid}/reopen` — a to-do marked
    Done by mistake comes back (`connections.reopen_outstanding`)."""
    require_tenant(request)
    return Response(w6_connections.reopen_outstanding(_actor(request), todo_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_update_note(request: Any, connection_id: Any, todo_id: Any) -> Response:
    """`POST /connections/{id}/outstanding-work/{tid}/edit` — the author edits
    their own note (`connections.update_note`)."""
    require_tenant(request)
    return Response(
        w6_connections.update_note(_actor(request), todo_id, title=_payload(request).get("title"))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def connection_add_unit(request: Any, connection_id: Any) -> Response:
    """`POST /connections/{id}/units` — *Add unit* with its services
    (`connections.add_unit_to_build`)."""
    require_tenant(request)
    return Response(
        w6_connections.add_unit_to_build(_actor(request), connection_id, _payload(request))
    )


urlpatterns = [
    # CR-038 A1 · S64. The literal `settings/…` routes live here now — see the
    # comment on the views above. The per-service path is a str converter, not
    # uuid: services are CODES ("electric") in every URL of this API.
    path("settings/read-validation", read_validation_settings),
    path("settings/read-validation/<str:service>", read_validation_service_settings),
    # CR-030 W6 task 6.12 · S86 `NCT-01`. Registered from metering because
    # metering owns `connections` (B2 r4 / B18 §5.4.6).
    # ⚠ ONE LINE, TWO VERBS (CR-070 wave B). `GET` is the worklist and `POST`
    # is `create_connection`; both are served by the `connections` view above,
    # because Django reaches only the first view registered on a path.
    path("connections", connections),
    # CR-030 W6 tasks 6.10 / 6.13 / 6.14 · the four doors S87 and S88 need.
    # ⚠ The literal `commit` is a SUBPATH of an id, not a sibling of it, so no
    # ordering trap arises here — unlike `routes/next-code` above. The bare id
    # route is registered AFTER it for the same reason `routes/next-code` sits
    # above `routes/<uuid:route_id>`: a literal segment must never be reachable
    # only by having beaten a converter. `<uuid:…>` would not match `commit`
    # today, so this ordering is a habit rather than a fix — and the habit is
    # what stops the next literal (`connections/export`, say) from being
    # swallowed the day somebody registers it with a looser converter.
    # `DEF-MET-5441` — THE WIZARD'S OWN DOOR. No id in the path, because
    # `BR-MET-112` means no connection row exists before the last step; the
    # orchestration is `commit_new_connect`'s, in one transaction. Registered
    # ABOVE the id routes on the habit the comment above names.
    path("connections/message-templates", connection_message_templates),
    path("connections/quote-preview", connection_quote_preview),
    path("connections/commit", connection_commit_new),
    path("connections/<uuid:connection_id>/commit", connection_commit),
    # ── CR-070 wave B · US-WRK-002 — the thirteen finished writers get a door.
    # ⚠ ORDERING IS LOAD-BEARING HERE, AND IT IS THE HABIT THE COMMENT ABOVE
    # NAMES. Every literal sub-path is registered BEFORE the bare `<uuid:…>` id
    # route, so no literal is reachable only by having beaten a converter — the
    # day somebody registers `connections/<str:something>` the order is what
    # stops these thirteen from being swallowed.
    path("connections/<uuid:connection_id>/services", connection_add_service),
    path(
        "connections/<uuid:connection_id>/services/<uuid:connection_service_id>/transition",
        connection_service_transition,
    ),
    path("connections/<uuid:connection_id>/submit", connection_submit),
    path("connections/<uuid:connection_id>/hold", connection_hold),
    path("connections/<uuid:connection_id>/release", connection_release),
    path("connections/<uuid:connection_id>/cancel", connection_cancel),
    path("connections/<uuid:connection_id>/waiting-on", connection_waiting_on),
    path("connections/<uuid:connection_id>/outstanding-work", connection_mark_outstanding),
    path(
        "connections/<uuid:connection_id>/outstanding-work/<uuid:todo_id>/close",
        connection_close_outstanding,
    ),
    # CR-162-BRC10 — literal sub-paths above the bare id route, on the habit
    # the comment above names.
    path(
        "connections/<uuid:connection_id>/outstanding-work/<uuid:todo_id>/reopen",
        connection_reopen_outstanding,
    ),
    path(
        "connections/<uuid:connection_id>/outstanding-work/<uuid:todo_id>/edit",
        connection_update_note,
    ),
    path("connections/<uuid:connection_id>/todos", connection_todos),
    path("connections/<uuid:connection_id>/activation", connection_activation),
    path("connections/<uuid:connection_id>/activate", connection_activate),
    path("connections/<uuid:connection_id>/units", connection_add_unit),
    path("connections/<uuid:connection_id>/owner-account", connection_owner_account),
    path("connections/<uuid:connection_id>/charges/tag", connection_tag_charges),
    path(
        "connections/<uuid:connection_id>/units/<uuid:unit_id>/characteristics/<str:key>",
        connection_unit_characteristic,
    ),
    # CR-126-BRC07 · the property's Build tab, filled in one call. A LITERAL
    # sub-path of an id, registered above the bare id route on the same habit
    # the thirteen above it follow — `<uuid:…>` would not match `record`, so
    # this ordering states the intent rather than fixing a bug.
    path("connections/<uuid:connection_id>/record", connection_build_record),
    path("connections/<uuid:connection_id>/fees", connection_add_fee),
    path(
        "connections/<uuid:connection_id>/messages/<str:code>/send",
        connection_message_send,
    ),
    path(
        "connections/<uuid:connection_id>/messages/<str:code>/preview",
        connection_message_preview,
    ),
    path("connections/<uuid:connection_id>", connection_detail),  # S88 `NCT-02`
    path("work-orders/<uuid:work_order_id>/field-result", work_order_field_result),
    path("work-orders/<uuid:work_order_id>/accept", work_order_accept),
    # BR-MET-106 (CR-030 W3 T3.8). Registered from metering because metering
    # owns the table — see `account_usage`.
    path("accounts/<uuid:account_id>/usage", account_usage),
    # CR-038 W5 task 8 — the METER half of BR-MET-106, per register.
    path("assets/<uuid:asset_id>/usage", asset_usage),
    path("premises", premises),
    path("premises/types", premises_types),
    # CR-094 capture lane E · PO 2026-09-15 — the register's own address search.
    # ⚠ A literal above `premises/<uuid:premises_id>`: the uuid converter would
    # not match the word anyway, but the order states the intent rather than
    # relying on it, exactly as `premises-owners/unmatched` does below.
    path("premises/picker", premises_picker),
    path("premises/imports", premises_imports),
    path("premises/imports/commit", premises_imports_commit),
    path("premises/<uuid:premises_id>", premises_detail),
    path("premises/<uuid:premises_id>/deactivate", premises_deactivate),
    # CR-089 wave D — the status dialog reads one and posts the other.
    path("premises/<uuid:premises_id>/status-change", premises_status_change),
    path("premises/<uuid:premises_id>/status", premises_status),
    # CR-039 wave C tasks 12-13 (BR-MET-150/151). `premises-owners/unmatched`
    # is listed BEFORE the `<uuid>` detail path so the literal wins -- a bare
    # `<uuid:owner_id>` would not match the word anyway, but the order states
    # the intent rather than relying on it.
    path("premises-owners", premises_owners),
    path("premises-owners/unmatched", premises_owners_unmatched),
    # ── DEF-650 (BR-MET-400/401) — the CHECK the PO asks for ────────────────
    # ⚠ ABOVE the `<uuid:owner_id>` route, for the same reason `unmatched` is:
    # a literal segment listed under a converter route is one a reader has to
    # reason about rather than read. (The `uuid` converter would not in fact
    # match `resolve`, so this is legibility, not a bug being avoided — said
    # plainly because a comment that claims a guarantee it does not give is
    # hard-won law 1.)
    path("premises-owners/resolve", premises_owners_resolve),
    path("premises-owners/<uuid:owner_id>", premises_owner_detail),
    path("premises-owners/<uuid:owner_id>/deactivate", premises_owner_deactivate),
    path(
        "premises-owners/<uuid:owner_id>/master-account",
        premises_owner_master_account,
    ),
    path("premises/<uuid:premises_id>/match-owner", premises_match_owner),
    path("premises/<uuid:premises_id>/lends", premises_lends),  # CR-089 wave E
    path(
        "premises/<uuid:premises_id>/units/next-free", premises_units_next_free
    ),  # CR-176-BRC10 rule (1)
    # CR-038 W6 · BR-MET-125 — the premises-level master-vs-subs report
    path(
        "premises/<uuid:premises_id>/submeter-reconciliation",
        premises_submeter_reconciliation,
    ),
    path("units", units),
    # ⚠ MUST sit above `units/<uuid:unit_id>` or the literal is read as an id.
    path("units/number-preview", unit_number_preview),  # CR-089 wave E · BR-MET-1165
    # `A3` · `DEF-MET-6796` — the service gap. ABOVE `units/<uuid:unit_id>` is
    # not required (that pattern is uuid-typed and cannot swallow a word), but
    # it sits with its sibling literal route so the two are read together.
    path("premises/number-preview", premise_number_preview),  # CR-089 wave B · BR-MET-1165
    path("premises/same-address", premises_same_address),  # CR-177-BRC10 · BR-MET-1190
    path("premises/owner-search", premises_owner_search),  # CR-177-BRC10 · BR-MET-1195
    path("units/plan-assignments/bulk", unit_plan_assignments_bulk),
    path("units/<uuid:unit_id>", unit_detail),
    path("units/<uuid:unit_id>/deactivate", unit_deactivate),
    path("units/<uuid:unit_id>/status-change", unit_status_change),
    path("units/<uuid:unit_id>/status", unit_status),
    path("units/<uuid:unit_id>/move", unit_move),  # BR-MET-095 (CR-024)
    path("units/<uuid:unit_id>/move-preview", unit_move_preview),  # CR-089 wave J
    path("units/<uuid:unit_id>/plan-assignments", unit_plan_assignments),
    path("units/<uuid:unit_id>/assets", unit_assets),  # B18 W5 T5.2
    path("units/<uuid:unit_id>/account", unit_account),  # CR-089 wave I
    path("units/<uuid:unit_id>/pricing", unit_pricing),  # B18 W5 T5.3
    path("routes", routes),
    # CR-006 · the wizard's own reads. Registered BEFORE `<uuid:route_id>` so
    # a literal segment can never be swallowed by the id converter.
    path("routes/next-code", route_next_code),
    path("routes/premises-picker", route_premises_picker),
    path("routes/meter-picker", route_meter_picker),
    # MQ-033 (PO 2026-10-24) — the reader, from Reads → cycle → Routes.
    path("routes/reader", route_reader),
    path("routes/reader-choices", route_reader_choices),
    path("routes/<uuid:route_id>", route_detail),
    path("routes/<uuid:route_id>/deactivate", route_deactivate),
    # CR-029 RC-W3b — the two route surfaces RC-W1 gave tables and no path.
    path("routes/<uuid:route_id>/premises-order", route_premises_order),  # D3 + D11
    path("routes/<uuid:route_id>/route-sheet", route_sheet_view),  # CR-038 W5 · RDS-01
    path("routes/<uuid:route_id>/read-windows", route_read_windows),  # D1
    path("routes/<uuid:route_id>/accounts", route_accounts),  # SET-06D.accounts (D12)
    path("cycles", cycles),
    path("cycles/next-code", cycle_next_code),
    path("cycles/coverage", cycle_coverage),
    path("cycles/<uuid:cycle_id>/chase-list", cycle_chase_list),  # US-MET-018 (CR-038 W1)
    path("cycles/<uuid:cycle_id>/route-sheet", cycle_sheet_view),  # BR-MET-162 · DEF-898
    # CR-054 W1 tasks 4/5 — the pre-filled reading sheet, and the count RDS-03
    # stage 2's button names. `/summary` is registered FIRST so the literal
    # segment can never be swallowed; both sit above the bare `<uuid:cycle_id>`
    # for the same reason the reads routes do.
    path("cycles/<uuid:cycle_id>/reading-sheet/summary", cycle_reading_sheet_summary),
    path("cycles/<uuid:cycle_id>/reading-sheet", cycle_reading_sheet),
    path("cycles/<uuid:cycle_id>", cycle_detail),
    path("reads", reads),
    path("reads/template", reads_template),
    path("units/unit-types", unit_types),  # DEF-MET-5656 — the clerk's picker
    path("reads/read-methods", read_methods),  # CR-038 W3 - the S28 step-1 tag
    path("reads/needs-attention", reads_needs_attention),
    path("reads/estimate", reads_estimate),
    # CR-038 W5 task 7 — bulk operations on the reads list. Both are POSTs
    # on the collection, ABOVE `reads/<uuid:read_id>` so a literal segment
    # is never shadowed by the uuid converter.
    path("reads/bulk-fix", reads_bulk_fix),
    path("reads/bulk-estimate", reads_bulk_estimate),
    # CR-038 W5 task 6 — what the quick single-read MODAL draws first.
    path("reads/quick-context", reads_quick_context),
    path("reads/<uuid:read_id>", read_detail),
    path("reads/<uuid:read_id>/supersede", read_supersede),
    path("reads/<uuid:read_id>/billed-correction", read_billed_correction),
    # `/dispute/clear` before `/dispute` is not required by Django's resolver
    # (paths are exact, not prefixes) but keeps the pair readable as a pair.
    path("reads/<uuid:read_id>/dispute/clear", read_dispute_clear),
    path("reads/<uuid:read_id>/dispute", read_dispute),
    path("read-batches", read_batches),
    path("read-batches/<uuid:batch_id>", read_batch_detail),
    path("read-batches/<uuid:batch_id>/validate", read_batch_validate),
    path("read-batches/<uuid:batch_id>/post", read_batch_post),
    path("read-batches/<uuid:batch_id>/post-receipt", read_batch_post_receipt),
    # CR-054 W4 task 16 (BR-MET-941). ONE path with a `kind` query parameter,
    # exactly as `imports/{id}/results.csv` is: two representations of one
    # resource, and two endpoints would be two places for the refusals and the
    # streaming to drift apart. Registered ABOVE the bare `rows/…` paths for the
    # habit this table already keeps — `<uuid:…>` would not match `results.csv`
    # anyway, so this is legibility rather than a trap being avoided.
    path("read-batches/<uuid:batch_id>/results.csv", read_batch_results_csv),
    # CR-038 W7 task 5 (OQ-042 closure). Same shape as `/post` above — a verb
    # subpath on the batch resource, the house grammar the eleven reads routes
    # already follow.
    path("read-batches/<uuid:batch_id>/cosign", read_batch_cosign),
    # BR-MET-051 (CR-038 W4). The literal segments are registered BEFORE the
    # bare row path so nothing can swallow them — `<int:row_no>` would not
    # match `demand-reset` anyway, but the three stay together so a reader sees
    # the pair as a pair (the `/validate` + `/post` precedent above).
    path("read-batches/<uuid:batch_id>/demand-reset", read_batch_demand_reset),
    path(
        "read-batches/<uuid:batch_id>/rows/<int:row_no>/demand-reset",
        read_batch_row_demand_reset,
    ),
    path("read-batches/<uuid:batch_id>/rows/<int:row_no>", read_batch_row),
    path("read-batches/<uuid:batch_id>/rows/<uuid:row_id>/delete", read_batch_row_delete),
    # CR-023 · stages 1–3 of the recorded runner. `/columns` is registered
    # before nothing else can swallow it — the run id is a uuid converter, so a
    # literal trailing segment is unambiguous, but the three stay together so a
    # reader sees the stage order in the routing table.
    path("imports", imports),
    path("imports/sample", import_sample),
    path("imports/<uuid:run_id>", import_run_detail),  # CR-026 — the poll surface
    path("imports/<uuid:run_id>/columns", import_columns),
    path("imports/<uuid:run_id>/transform", import_transform),
    path("imports/<uuid:run_id>/validate", import_validate),
    path("imports/<uuid:run_id>/rows/<int:row_no>", import_row_fix),  # CR-028 inline fix
    path("imports/<uuid:run_id>/save-mapping", import_save_mapping),  # BR-AST-048
    # Stages 4 and 5. Listed in the order an operator meets them so the routing
    # table reads as the workflow does, and `/load` — the only writer — sits
    # between the rehearsal it must agree with and the receipt it produces.
    path("imports/<uuid:run_id>/dry-run", import_dry_run),
    # PO ruling 2026-08-27 — post the opening balances a run is holding.
    path("imports/<uuid:run_id>/confirm-changeover", import_confirm_changeover),
    path("imports/<uuid:run_id>/load", import_load),
    path("imports/<uuid:run_id>/receipt", import_receipt),
    # CR-047 — the two files a migration comes out as. ONE path, one `kind`
    # query parameter: they are two representations of one resource (the run's
    # result), and two endpoints would be two places for the refusals and the
    # streaming to drift apart — `import_sample`'s own precedent.
    path("imports/<uuid:run_id>/results.csv", import_results_csv),
    path("imports/<uuid:run_id>/rollback", import_rollback),
]

# CR-187-BRC10 — the native field app's route reading (`07-endpoints.md` N1, N5,
# N6, N12). Its own module so this file does not grow a seventh concern; mounted
# here so `config/urls.py` needs no change. Every path is `work/mobile/…` and
# none collides with `apps.work.api`'s (`today`, `devices`, `jobs/…`, …).
from apps.metering import field_reads_api  # noqa: E402

urlpatterns += field_reads_api.urlpatterns

# MQ-033 (`CR-192-BRC10`) — Settings → Reads: the utility's read FORMATS, their
# pointers on cycles and routes, and the handset's copy of a version. Its own
# module for the same reason; mounted ABOVE the bearer line below so the
# `work/mobile/read-formats/…` path takes the field app's token too.
from apps.metering import read_formats_api  # noqa: E402

urlpatterns += read_formats_api.urlpatterns

# DEF-MET-10609 (decision log 2026-10-26, PO *"yes do it"*) — Settings →
# Reference data → Readings → Can't-read reasons: the one list route readings
# and job readings both use. Its own module, the read formats' reason.
from apps.metering import cant_read_reasons_api  # noqa: E402

urlpatterns += cant_read_reasons_api.urlpatterns

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@d76f5b4 (story+rules snapshot hash — EP-MET-01 lead story; co-packet EP-MET-02@8f2ab3c)
# packet: US-MET-016@c81d5a7 (EP-MET-04 — POST /reads/{id}/billed-correction + the staged-row delete)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (PATCH /imports/{run}/rows/{row_no} inline fix + POST /imports/{run}/save-mapping (BR-AST-048)) · AMENDED 2026-08-25 by the CR-030 W5 P2 lane (B18 W5 tasks 5.2/5.3 — `GET /units/{id}/assets` groups on the POST-CR-028 `asset_types.category` (BR-AST-004), never on the (sub)/(master) qualifier, and states `reading_expected`'s absence against DEF-495; `GET /units/{id}/pricing` forwards rating's own plan/schedule/charge/tax strings VERBATIM and computes NO money — B18's worked month is NOT served and says so, because nothing prices a plan outside a bill run and no signed rule states the consumption it would be priced at. An OQ is OWED for that; the absence carries `tracks: null` rather than a fabricated id) · AMENDED 2026-08-26 by the CR-034 (b) WORKEDMONTH lane (CR-034 (b) — `GET /units/{id}/pricing` accepts optional `period_start`/`period_end`, BOTH or NEITHER, parsed by `date.fromisoformat` and nothing looser; a half window and a reversed one refuse by name. With neither the answer is byte-identical to what it served before. ⚠ The three refusals reuse EXISTING catalogue keys (`metering.lookups.required`, `metering.cycle.bad_date`, `billing.run.error.periodOrder`) because G32 is a ratchet at zero with no register and this lane may not write catalogue copy — three precise sentences are OWED and handed over, one of them to move the reversed-period refusal out of billing's namespace. ⚠ `openapi/schema.json` REGENERATED — `manage.py export_openapi`, one line, this endpoint's description only; the committed snapshot is asserted by `tests/test_be11_openapi.py` TC-05 and went RED on the stale copy. ⚠ AND THE TWO QUERY PARAMS ARE NOT DECLARED IN THE SCHEMA: no endpoint in metering, billing or rating uses `@extend_schema`, so drf-spectacular infers no query parameter anywhere in this product. Consistent, and REPORTED rather than fixed one-off) · AMENDED 2026-08-26 by lane PAYLOAD (DEF-766 — the reject list travels as a WINDOW: run_dict serves REJECT_WINDOW_DEFAULT = 50 rejects plus rejects_window {total, offset, limit}, GET /imports/{id} takes ?reject_offset/?reject_limit, and the stage-3 table pages through the SERVER. The poll surface was building the whole list with every row's raw cells every two seconds — 4.28 MB on the PO's 9,881-reject run. Measured: a 600-reject run answers 26,401 B where the unbounded list answered 273,302 B, and the payload no longer grows with the reject count at all — 60 rejects 26,392 B, 600 rejects 26,401 B)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: [W2 reads lane 2026-08-10] eleven /reads + /read-batches endpoints added with NO 11b row to follow — the reads surface has no contract entry yet, so they follow the house grammar (resource, then verb-as-subpath) and are REPORTED for the A11 addendum · POST /read-batches/{id}/post commits SYNCHRONOUSLY: BR-MET-055 asks for a background job and this deployment registers no BE-07 job store, so answering a 202 with no job record behind it was refused (same posture as rating POST /rate-changes and audit's export) — REPORTED · GET /reads/needs-attention serves `missing: null` with a stated reason because the BR-MET-049 plan-driven completeness computation is US-MET-018 and is not built · 06-backend/openapi/schema.json is now STALE (these endpoints plus the concurrent customers lane's /accounts): `python manage.py export_openapi` regenerates it — deliberately NOT run here with three lanes live, REPORTED
# exceptions: urlpatterns exported but NOT included in config/urls.py (outside territory — one-line include for the wiring lane) · DELETE /premises/{id} and DELETE /units/{id} added for the capability-matrix Delete row action (11b §2.5 lists only deactivate) — reported · the bulk path has no staged id because US-MET-004 §5 forbids persistence in v1 — E2 vs 11b's 3-step contract, reported · [path-tenancy lane 2026-08-10] 201 Location headers are absolute inside the request's tenant prefix (core.tenancy.tenant_path)
# exceptions: [US-MET-013 dispute lane 2026-08-16, DEF-046] two routes added
#         with no 11b row to follow — the reads surface still has no contract
#         entry, so `/reads/{id}/dispute` and `/reads/{id}/dispute/clear` follow
#         the same house grammar the eleven reads endpoints already do
#         (resource, then verb-as-subpath) and are REPORTED for the A11
#         addendum alongside them. `/dispute/clear` carries `SystemAdminOnly` at
#         the router AND @require_role(SYSTEM_ADMIN) in the service (BR-SHL-025
#         defence in depth) because the OQ-043 closure gives the release to that
#         role alone. Neither route can change a reading: a dispute is a claim
#         ABOUT a number and the correction doors stay `/supersede` and
#         `/billed-correction`
# exceptions: [CR-023 P3/P4 lane 2026-08-21] four routes added with no 11b row
#         to follow — `POST /imports`, `GET /imports/{id}/columns`, `POST
#         /imports/{id}/transform`, `POST /imports/{id}/validate`. They are
#         B15 §12 rows 1–4 and they follow the house grammar (resource, then
#         verb-as-subpath) like the eleven reads routes already do; REPORTED
#         for the A11 addendum alongside them. **They SUPERSEDE `POST
#         /premises/imports` + `/commit` and BOTH REMAIN MOUNTED ON PURPOSE**
#         (B15 §7A: `AddPremisesWizard`'s bulk path calls the old pair and
#         PRM-07 step 1 still offers it, so deleting it before the recorded
#         path has a screen would remove a working feature). A later commit
#         must move the wizard onto the runner and retire the pair, saying
#         what it retires. ⚠ **NONE of these four writes a premises** — B15
#         §16 TC-1, proved RED first. `/dry-run`, `/load`, the receipt, the
#         run list and the rollback (B15 §12 rows 5–10) are deliberately NOT
#         mounted: a route that 501s is a promise a screen will call.
#         The endpoints call `apps.metering.import_runs` directly rather than
#         `services` — that module holds its own ORM against metering's OWN
#         tables (the `sample_data.py` posture) so a concurrent CR-024 lane
#         editing `services.py` and this lane never touch one file; no table
#         outside metering is written, so LAW 0's module boundary is intact.
#         ⚠ `06-backend/openapi/schema.json` IS STALE and these four routes are
#         four of the FORTY paths missing from it — the other 36 predate this
#         lane, so `tests/test_be11_openapi.py::test_be11_tc05` was RED before
#         it and is RED after it. NOT regenerated here: the export reads the
#         WHOLE URLconf, so running it would commit 36 other lanes' contract
#         shape inside a commit about CR-023 (law 11 mechanism five). Filed as
#         `DEF-513` — DEF-145 is the same defect, marked *fixed*, recurred
# exceptions: [CR-023 W2 stage-4/5 lane 2026-08-22] five more routes with no
#         11b row — `GET /imports` (the run list), `POST /imports/{id}/dry-run`,
#         `POST /imports/{id}/load`, `GET /imports/{id}/receipt` and `POST
#         /imports/{id}/rollback` (B15 §12 rows 5–10). House grammar again;
#         REPORTED for the A11 addendum with the four above. ⚠ **`/load` IS THE
#         FIRST ROUTE IN THIS MODULE'S IMPORT PATH THAT WRITES A PREMISES** —
#         everything before it rehearses.
#         ⚠ **BR-MET-098's APPROVER IS ENFORCED HERE AND IN THE ENGINE.** This
#         line said *"HERE AND NOWHERE ELSE"* until 2026-08-27 (`DEF-545`,
#         closed): `import_runs.load` read `approved` as a bare boolean and
#         asked nothing about who set it, so this file was the only thing
#         standing between a Billing Clerk and their own second approval — ONE
#         layer where BR-SHL-025 asks for two. `_load_locked` now carries its
#         own BR-MET-098 refusal. This file still refuses `approved` from
#         anyone but a System Admin (`/discounts/{id}/versions/{vid}/approve`'s
#         posture, the same pair of roles BR-RAT-091 uses) and is the STRICTER
#         of the two on purpose — see `import_load`'s docstring.
#         ⚠ `import_receipt` calls `import_runs._run` because the module
#         publishes no `read_receipt(run_id)` and an ORM query here is forbidden
#         (B8/LAW 0). Tenant-scoped, same app, `NotFoundError` across tenants —
#         the boundary holds; the underscore is REPORTED.
#         ⚠ **THREE OF THESE FIVE ARE MOUNTED OVER AN ENGINE THAT REFUSES THEM
#         TODAY, AND THAT IS DELIBERATE.** `import_runs._run()` rejects every
#         run whose status is `loaded` or `rolled_back`, which is the ONLY
#         status `/receipt` and `/rollback` apply to and is also what makes the
#         load's own idempotency branch unreachable — one guard, three dead
#         behaviours, filed as `DEF-541`. The routes are correct and answer the
#         moment that guard takes its allowed statuses from its caller; a route
#         withheld now would have to be added by a later lane that no longer
#         remembers why. The SCREEN depends on neither: WFL-01 stage 5 draws the
#         receipt `/load` already answered with, and PRM-04's rollback icon
#         ships disabled with this reason (BR-SHL-025).
#         Five more defects were found by the first tests that actually RUN the
#         load and are REPORTED, not fixed here: `DEF-540` (a resolved
#         `premises_type` cannot be written — the column is a FK and the loader
#         passes the code), `DEF-542` (a mapped AREA is checked and then
#         silently dropped), `DEF-543` (`upsert` can never update a premises —
#         a tier-1 uniqueness rule rejects every row first), `DEF-544` (the dry
#         run reports every unit that names a plan as unplanned) and `DEF-547`
#         (the 5% bar fires AT 5%, where the rule says "exceed").
# exceptions: [CR-030 W6 A-CONN lane 2026-08-25, task 6.12] ONE route added with
#         no 11b row and no US-ID — `GET /connections`, which B18 §5.4.6 lists
#         by name and hard-won law 8 has nothing owning (S86 has no story;
#         REPORTED). House grammar, resource-only. ⛔ **`?segment=` serves `all`
#         and raises `NotImplementedError("OQ-371")` for every other value**,
#         the `finance/cost-reconciliation/download` posture: a named refusal,
#         not a 404. The four tabs `NCT-01` draws are carried on `unavailable`
#         so the screen disables them WITH the reason rather than calling the
#         route to discover it. ⚠ The envelope is assembled here instead of by
#         `StandardPagination` because `connection_reads` pages BEFORE it builds
#         rows (three derivation queries per row); the four DRF keys are
#         identical, deliberately — one shape. ⚠ **NOTHING CALLS THIS YET** —
#         the Accounts "New connects" tab still renders its placeholder; the
#         frontend half of 6.12 is not this lane's and is REPORTED rather than
#         left to add up (r11 step 2b). ⚠ `openapi/schema.json` gains a
#         forty-first missing path and was NOT regenerated (law 11 mechanism
#         five — the export reads the whole URLconf).
# exceptions: [CR-038 W1 lane 2026-08-26, US-MET-018] ONE route added with no
#         11b row — `GET /cycles/{id}/chase-list` (BR-MET-057's chase list;
#         house grammar, resource then verb-as-subpath) — **the A11 row is
#         OWED**, REPORTED for the A11 addendum alongside the routes above.
#         Two existing routes changed SHAPE, no new path: `GET /reads` now
#         honours `f.status=pending` by serving the DERIVED pending entries
#         (id-less, `derived: "pending"` — US-MET-012 §1 "derived, not
#         stored"; a stored-status filter would return an empty page that
#         reads as "nothing pending"), and `GET /read-batches/{id}` + the
#         validate summary now carry `cycle_coverage` (None with
#         `cycle_coverage_absent_reason` for a cycle-less batch). The
#         needs-attention payload's `missing` stops being null and
#         `missing_unavailable_reason` is GONE — the frontend null-branch
#         (the "—" chip) keeps rendering only until the W2 screen lane reads
#         the number; REPORTED to the coordinating session. `openapi/schema
#         .json` was NOT regenerated (law 11 mechanism five — the export reads
#         the whole URLconf).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# `CR-187-BRC10` — the native field app's bearer token on the route-reading
# routes too (they live under `work/mobile/` in THIS module's list, so the one
# line in `apps/work/api.py` does not reach them). Same helper, same prefix.
from apps.identity.native_auth import accept_native_bearer  # noqa: E402

accept_native_bearer(urlpatterns, "work/mobile/")
