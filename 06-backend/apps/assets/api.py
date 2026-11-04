# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (GET /assets — 3 tabs, search, status filter) ·
#           US-AST-002 (POST /assets) · US-AST-003 (PATCH/DELETE /assets/{id}) ·
#           US-AST-004 (GET /assets/{id}) · US-AST-006 (GET .../assignments,
#           .../maintenance) · US-AST-007 (POST .../maintenance) · US-AST-008
#           (POST .../retire) · US-AST-009 (POST .../reassign, /bulk-assign) ·
#           US-AST-010 (POST /assets/imports → GET → POST .../commit)
#           Screens: S49–S55
# Rules:    BR-AST-005/006 (filter + action semantics) · BR-AST-032 (roles;
#           server-enforced — UI gating is convenience, A4/BR-SHL-025) ·
#           BR-AST-013 (delete gate → 409 with a retire pointer) · BR-AST-033
#           (duplicate asset # → 409) · BR-AST-044 (both classifications on the
#           row + detail payloads; `f.meter_type` list filter, BR-SHL-011) ·
#           A11 Addendum r2 / 11b §2.12
# Tests:    06-backend/tests/test_us_ast_*.py (API halves per story file)
# Impacts:  config/urls.py inclusion (wiring lane — `urlpatterns` exported
#           here, exactly as apps/tenancy/api.py does) · FI-01 typed client
# ───────────────────────────────────────────────────────
"""assets API endpoints per 11b §2.12 (ratified via A11 Addendum r2).

THIN by law (B8/LAW 0): writes through services, reads through selectors, no
ORM here. Refusals are catalog exceptions rendered by the BE-02 handler.

Reported deviations:
- `GET /assets/{id}/reads` IS SERVED as of CR-028 AST-W2 (2026-08-22) —
  DEF-475 closed: metering's read list gained the per-asset narrowing this
  route needed, so an empty history is now a TRUE claim the endpoint may make.
  (The pre-W2 text here recorded why it was deliberately absent.)
- the import endpoints answer 201/200 synchronously rather than the 202 + job
  poll the 11b row names: core.jobs has no registered store on this deployment
  (apps.tenancy.Job exists; the store adapter lands with the /jobs/{id}
  story), and a 202 promising a poll URL with no job row behind it is a lie
  the kernel refuses to tell.
"""

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.assets import selectors, services
from core import errors
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant, tenant_path

# BR-AST-041 capability row: filters status · service · premises · assigned ·
# test-due, plus the tab partition (BR-AST-004) and — since BR-AST-044 — BOTH
# classifications: `f.type` (asset_types) and `f.meter_type` (meter_types).
# Grammar is BR-SHL-011's `f.‹name›`; unknown params are ignored, never an error.
ASSET_FILTERS = (
    "status",
    "service",
    "premises_id",
    "assigned",
    "test_due",
    "tab",
    "type",
    "meter_type",
    # CR-089 G1 / BR-AST-500: the service connection's size class, as TEXT.
    # `none` selects the rows carrying no size — the same word `f.meter_type`
    # already uses for the same absence, so a clerk learns one.
    "size_class",
    # DEF-MET-8362: the assets CURRENTLY seated on one unit. The unit's Assets
    # tab asked for the PREMISES' registry at `per=200` and narrowed it in the
    # browser, so past 200 assets on a premises its rows drew '—'. A unit's
    # list is a server filter and a server page like every other (NFR-3).
    "unit_id",
)


def _actor(request: Any) -> Any:
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="assets.payload_not_object")
    return data


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # writes re-gated in services (BR-AST-032)
def assets(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        # `CR-161-BRC10` W2 — Add asset's door (`DEF-AST-9171`).
        result = services.create_asset(
            _actor(request), _payload(request), custom_fields_screen="S51"
        )
        response = Response(result, status=201)
        response["Location"] = tenant_path(request, f"/assets/{result['id']}")
        return response
    params = parse_list_params(
        request.query_params,
        allowed_sorts=tuple(selectors.ASSET_SORTS),
        default_sort=selectors.ASSET_DEFAULT_SORT,
        allowed_filters=ASSET_FILTERS,
    )
    # ── CR-089 G1 · `?terms=` — the words a clerk is holding ────────────────
    #
    # OPTIONAL and ADDITIVE: without it this route answers exactly as it did.
    # With it, the free text is read against the TENANT's own catalogues, the
    # filters it resolves are merged UNDER the caller's explicit `f.` params
    # (an explicit filter is a decision and a typed word is a guess, so the
    # decision wins), and the reading is served back as `resolved`.
    #
    # ⚠ **THE CHIPS AND THE FILTER ARE ONE ANSWER, WHICH IS WHY THIS IS NOT A
    # SEPARATE ENDPOINT.** A screen that asked one route what the words mean
    # and a second route for the rows could draw *Water 5/8"* over a list
    # filtered by something else, and nothing would ever go red. Here the rows
    # below are filtered by `resolved["filters"]` itself.
    terms = (request.query_params.get("terms") or "").strip()
    resolved = selectors.resolve_search_terms(terms) if terms else None
    filters = dict(params.filters)
    if resolved is not None:
        filters = {**resolved["filters"], **filters}
    rows = selectors.asset_list(
        q=params.q, filters=filters, sort=params.sort, direction=params.dir
    )
    # ⚠ `DEF-MET-4962` / `DEF-MET-4951` — `rows` IS A QUERYSET AND THAT IS THE
    # WHOLE FIX. It used to be a materialised Python list, so this line sliced
    # in memory and no `LIMIT` or `OFFSET` ever reached SQL while the envelope
    # below reported a perfectly correct `count`/`next`/`previous`. Measured on
    # `pine-hill` before: `f.assigned=true` cost 111 queries, `f.service=water`
    # 209, the two together 319 to return 53 rows. All three are 2 now.
    paginator = StandardPagination()
    page = paginator.paginate_queryset(rows, request)
    # `DEF-5745` — the page's rows, with EVERY cross-row read resolved once for
    # the whole page (`selectors.asset_page_rows`). ⚠ **THIS COMMENT NAMED ONE
    # FIELD UNTIL 2026-09-19** — `CR-089` wave C `C4` batched `last_read` and
    # left the other five per-row reads inside `asset_dict`, so shaping a page
    # of 40 cost **201** queries and a page of 1,000 cost **5,001**. It is 6 and
    # 9 now. Measured, not asserted: `tests/test_def5745_registry_row_batching.py`.
    response = paginator.get_paginated_response(selectors.asset_page_rows(list(page or [])))
    if resolved is not None:
        response.data["resolved"] = resolved
    # ── `DEF-MET-4953` · the KPI strip's figures, SERVED ─────────────────
    #
    # ⚠ **IT RIDES THE LIST ANSWER RATHER THAN BEING ITS OWN ROUTE, FOR THE
    # REASON `terms` ABOVE GIVES.** A screen that asked one route for the rows
    # and a second for the strip could draw one tab's figures over another
    # tab's list, and nothing would ever go red. Here the tab is read from the
    # same `params` the rows were filtered by.
    #
    # The FIGURES are the tab's whole population and are deliberately NOT
    # narrowed by `q` or by the caller's filters — see `selectors.asset_kpis`
    # for why that is the existing meaning of these cards and not a new one.
    kpis = selectors.asset_kpis(str(params.filters.get("tab") or ""))
    if kpis is not None:
        response.data["kpis"] = kpis
    if params.filters.get("tab") == "behind_the_meter":
        # CR-028 debt sweep D4: the BTM tab's "Exported · <month>" KPI rides
        # the tab's own list answer — one extra metering-side query (DEF-324),
        # quantities with their explicit units, no money (BR-AST-025). Null
        # when the seam is unwired; the card then keeps its quiet dash.
        from apps.assets import seams

        response.data["export_rollup"] = seams.export_rollup_last_month()
    return response


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def asset_detail(request: Any, asset_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        # `CR-161-BRC10` W2 — Edit asset is the form that sends `custom_data`.
        return Response(
            services.update_asset(
                _actor(request), asset_id, _payload(request), custom_fields_screen="ASSET_EDIT"
            )
        )
    if request.method == "DELETE":
        services.delete_asset(_actor(request), asset_id)
        return Response(status=204)
    return Response(selectors.asset_detail(asset_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_number_preview(request: Any) -> Response:
    """CR-028 AST-W4 (AST-05 step 1): the series suggestion + the UNIQUE
    availability probe. A READ on tenancy's preview contract — nothing
    allocates, nothing advances (`selectors.asset_no_preview`); `available`
    is null when no number was asked about, never a guess."""
    require_tenant(request)
    type_code = request.query_params.get("type") or ""
    asset_no = (request.query_params.get("asset_no") or "").strip()
    return Response(
        {
            "suggested": selectors.asset_no_preview(type_code),
            "available": selectors.asset_no_available(asset_no) if asset_no else None,
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_stock(request: Any) -> Response:
    """CR-028 AST-W5 T1 (§10-D5 RULED: counts & costs ONLY): the Inventory
    tab's aggregate — uninstalled (behavior class `available`) grouped by
    type, with the honest-null costs. No reorder, no van, no stock table."""
    require_tenant(request)
    params = parse_list_params(request.query_params)
    return Response(selectors.stock_view(page=params.page, per=params.per))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_metered_services(request: Any) -> Response:
    """`GET /assets/metered-services` — BR-TEN-162 / DEF-901.

    Which utility services this tenant ACTUALLY METERS, read from its own
    asset register. The S64 read-validation page asks it before drawing a
    threshold form, because thresholds judge READINGS and a service with no
    meter produces none: the PO asked *"are these settings applicable to
    sewer"* of a page offering fourteen tunable inputs for a service priced as
    a percentage of water (BR-RAT-015).

    ⚠ **IT IS A READ OF THE ESTATE, NOT A LIST OF "UNMETERED SERVICES".** A
    utility that genuinely meters sewer gets `sewer` in this list and gets the
    form, with nothing to configure anywhere. See
    `selectors.metered_service_codes` for what counts as a meter and why
    lifecycle stage is deliberately not a predicate.

    `AnyTenantRole` on purpose: it is the same fact `GET /assets` already
    serves any tenant role, aggregated — no cost, no money, no identity — and
    the settings page that consumes it is behind its own A4 gate already.
    """
    require_tenant(request)
    return Response({"services": selectors.metered_service_codes()})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_size_banded_services(request: Any) -> Response:
    """`GET /assets/size-banded-services` — `DEF-AST-7660`.

    Which of this tenant's ENABLED services price by SIZE BAND, which do not,
    and which nobody has ruled. An assign form reads it to know whether the
    connection size is REQUIRED before the clerk presses `Assign ✓`, instead
    of finding out inside a bill run months later.

    ⚠ **IT EXISTS BECAUSE THE BROWSER MUST NOT INFER THIS.** See
    `selectors.size_banded_services` — the obvious client-side substitute is
    `DEF-3098`'s retired proxy and would refuse a solar install for a size
    that service does not have.

    ⚠ **THREE LISTS AND NOT A BOOLEAN PER SERVICE.** `not_ruled` is a real
    answer and collapsing it into `not_banded` would silently tell a screen
    that a blank size is lawful on a service nobody has been asked about —
    the prime directive resolved by a default. **It is EMPTY on every tenant
    today** (measured 2026-09-28): the one unruled thing is the DIMENSION
    `thermal_heat_steam`, and a dimension is not a service code. The list
    exists for the twelfth service, not for a case running now.

    `AnyTenantRole`: no money, no cost, no identity — it is a projection of
    ratified law plus the tenant's own enabled-service list, and every screen
    that consumes it is behind its own gate already, exactly like
    `GET /assets/metered-services` above.
    """
    require_tenant(request)
    return Response(selectors.size_banded_services())


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_lifecycle(request: Any) -> Response:
    """CR-028 AST-W5 T2 (§10-D3 RULED): the Lifecycle tab's three lists +
    the Asset value panel, ONE call (B16 §4.8's contract). NO GL sentence,
    no depreciation posting — the panel is BR-AST-047 arithmetic only."""
    require_tenant(request)
    params = parse_list_params(request.query_params)
    return Response(selectors.lifecycle_view(page=params.page, per=params.per))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_geo(request: Any) -> Response:
    """CR-028 AST-W5 T3 (§10-D6 RULED): every non-retired asset standing on a
    geocoded premises — the AST-03 map's markers, popup facts and filter
    vocabularies. No work-order fact (§10-D7)."""
    require_tenant(request)
    params = parse_list_params(request.query_params)
    return Response(selectors.geo_view(page=params.page, per=params.per))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_assignments(request: Any, asset_id: str) -> Response:
    """`GET /assets/{id}/assignments?page=&per=` — US-AST-006's Assignment
    history, SERVER-PAGED (`AST-B-24` · `DEF-MET-4995` · `NFR-3`).

    The envelope is `{count, next, previous, results}` — the same four names
    `GET /assets` and `GET /assets/{id}/work-orders` already answer with, so an
    asset detail screen reads ONE convention across all four of its lists
    instead of three different ones. `07-frontend/src/api/paginated.ts` is that
    convention's single declaration on the client side.
    """
    require_tenant(request)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.assignments_page(asset_id), request)
    return paginator.get_paginated_response(selectors.assignment_rows(list(page or [])))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_reads(request: Any, asset_id: str) -> Response:
    """CR-028 AST-W2 (DEF-475 closed): US-AST-005's Reads tab, SERVED — the
    asset's committed heads with BR-AST-029's typed pair folded per date.
    Quantities with explicit units only; no money (BR-AST-016/025)."""
    require_tenant(request)
    # ⚠ **THE PAGE IS FIFTY READ DATES, NOT FIFTY ROWS** (`AST-B-24`).
    # `asset_reads` folds BR-AST-029's typed pair into ONE row per read date, so
    # a three-register meter serves three rows for one date. Paging the ROWS
    # would cut a reading event across a page boundary — half a meter's
    # registers on page 1 and half on page 2 — so `count` here is the number of
    # READ DATES and a page's length varies with the register count. The
    # contract says so out loud (A11 Addendum r7) rather than leaving a client
    # to infer it from a page that is sometimes 50 and sometimes 150.
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.asset_read_dates_page(asset_id), request)
    return paginator.get_paginated_response(selectors.asset_reads_on(asset_id, list(page or [])))


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def asset_maintenance(request: Any, asset_id: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(
            services.log_maintenance(_actor(request), asset_id, _payload(request)), status=201
        )
    # CR-028 AST-W2 T7: rows + the server's lifetime total, the CHAR(3)
    # currency riding WITH the amounts (rule 2). `lifetime_cost` is null when
    # no entry carries a cost — never a fabricated $0.00.
    from apps.assets import seams

    # ⚠ **SPREAD, DO NOT PASS.** `get_paginated_response` builds a fresh
    # four-key body; a fifth key set on the result before handing it over is
    # dropped on the floor, which is exactly how `maintenance_index` never left
    # the server in `DEF-AST-4120` and every WORK ORDER cell on this same screen
    # became a dash. `lifetime_cost` and `currency` are siblings of the
    # envelope, not members of it.
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.maintenance_page(asset_id), request)
    response = paginator.get_paginated_response(selectors.maintenance_rows(list(page or [])))
    # The lifetime total is the SERVER's sum over EVERY costed entry, not over
    # the page — a total that changed when you turned the page would be a
    # different and wrong number. Null, never $0.00, when nothing carries a cost.
    response.data["lifetime_cost"] = selectors.maintenance_lifetime_cost(asset_id)
    response.data["currency"] = seams.tenant_currency()
    return response


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-AST-032: retire = System Admin only
def asset_retire(request: Any, asset_id: str) -> Response:
    require_tenant(request)
    return Response(services.retire_asset(_actor(request), asset_id, _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def asset_reassign(request: Any, asset_id: str) -> Response:
    require_tenant(request)
    return Response(services.reassign_asset(_actor(request), asset_id, _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def assets_bulk_assign(request: Any) -> Response:
    require_tenant(request)
    return Response(services.bulk_assign(_actor(request), _payload(request)))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def asset_imports(request: Any) -> Response:
    require_tenant(request)
    return Response(services.stage_import(_actor(request), _payload(request)), status=201)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def asset_import_detail(request: Any, batch_id: str) -> Response:
    require_tenant(request)
    return Response(selectors.import_batch(batch_id))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def asset_import_commit(request: Any, batch_id: str) -> Response:
    require_tenant(request)
    return Response(services.commit_import(_actor(request), batch_id, _payload(request)))


urlpatterns = [
    path("assets", assets),
    path("assets/bulk-assign", assets_bulk_assign),
    # Literal segment ABOVE the <uuid> routes — the AssetImportWorkflow route-
    # ordering lesson (DEF-520's shape), applied server-side too.
    path("assets/number-preview", asset_number_preview),
    # CR-028 AST-W5: the three tab reads — literal segments, above <uuid>.
    path("assets/stock", asset_stock),
    # DEF-901 / BR-TEN-162 — literal segment, above the <uuid> routes for the
    # same reason the three above it are.
    path("assets/metered-services", asset_metered_services),
    # DEF-AST-7660 — literal segment, above the <uuid> routes for the same
    # reason the four above it are.
    path("assets/size-banded-services", asset_size_banded_services),
    path("assets/lifecycle", asset_lifecycle),
    path("assets/geo", asset_geo),
    path("assets/imports", asset_imports),
    path("assets/imports/<uuid:batch_id>", asset_import_detail),
    path("assets/imports/<uuid:batch_id>/commit", asset_import_commit),
    path("assets/<uuid:asset_id>", asset_detail),
    path("assets/<uuid:asset_id>/reads", asset_reads),
    path("assets/<uuid:asset_id>/assignments", asset_assignments),
    path("assets/<uuid:asset_id>/maintenance", asset_maintenance),
    path("assets/<uuid:asset_id>/retire", asset_retire),
    path("assets/<uuid:asset_id>/reassign", asset_reassign),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-001@9d8d058 (story+rules snapshot hash — EP-AST-01 registry story; co-packets EP-AST-02/03/04@9d8d058)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-09 by story-coder (BR-AST-044 both-classifications lane) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-22 by the CR-028 AST-W2 lane (GET /assets/{id}/reads SERVED — DEF-475 closed; the maintenance GET answers {rows, lifetime_cost, currency} per T7) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (GET /assets/number-preview — the AST-05 suggestion + availability probe, a READ that allocates nothing; literal path above the uuid routes) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (GET /assets/stock · /assets/lifecycle · /assets/geo — the three new tab reads, thin per LAW 0, literal segments above the uuid routes)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [BR-AST-044 lane 2026-08-09] ruff✔(E4/E7/E9/F) black✔ migrate✔ makemigrations --check✔ (hand-written 0004 matches the model state) · suite `pytest tests -m "not golden and not isolation"` 593 passed / 8 skipped (587 baseline green + 6 new BR-AST-044 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (unchanged) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy STILL NOT INSTALLED in this environment (recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: urlpatterns exported but NOT included in config/urls.py (outside territory — one-line include for the wiring lane) · GET /assets/{id}/reads deliberately absent (US-AST-005 SKIPPED — meter_reads is W2) · imports answer synchronously instead of 202+job: core.jobs has no registered store on this deployment (reported) · BR-AST-044 lane 2026-08-09: ASSET_FILTERS gains `meter_type` (BR-SHL-011 `f.‹name›` grammar) so the registry filters on BOTH classifications; no new endpoint — the detail payload carries the third · [path-tenancy lane 2026-08-10] 201 Location headers are absolute inside the request's tenant prefix (core.tenancy.tenant_path)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
