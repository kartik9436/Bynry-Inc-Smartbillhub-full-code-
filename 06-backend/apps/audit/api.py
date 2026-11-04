# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-004 (GET /audit-log — the S61 viewer list) · US-AUD-005
#           (GET /audit-log/{id} — the detail drawer payload) · US-AUD-006
#           (POST /audit-log/export — 202 + job_id, 50k cap, self-audited) ·
#           US-AUD-008 (the ?archive opt-in routed at the cold partitions) ·
#           US-AUD-009 (GET/POST /reports/user-activity-audit — the A14
#           Compliance card's feed over this same dataset) · US-MET-020 /
#           US-AUD-007 (GET /retention/runs — the `archive_job_runs` ledger,
#           which existed in a migration, a command and core/archival.py and in
#           NO api.py anywhere: nobody could answer "has retention ever run?")
#           Screens: S61 (owned, + its Data-retention view) · S21/S50/premises Audit tabs (windows)
# Rules:    BR-MET-055 / BR-AUD-012 (retention is an AUTOMATIC scheduled job,
#           2 yr hot → archive, 7 yr total — NEVER manual, which is why the
#           retention route defines a `get` and nothing else) ·
#           BR-AUD-002 (read-only BY CONSTRUCTION — no create/update/delete verb
#           exists on this resource; HR-4 / 11b G8) · BR-AUD-007 (tenant-scoped
#           only, RLS-enforced; no cross-tenant view even for support) ·
#           BR-AUD-009 (System Admin + Executive; filter vocabulary; the six S61
#           columns; row → drawer) · BR-AUD-013 (server pagination, 2-yr hot
#           window default, EXPLICIT archive, never unbounded) · BR-AUD-014 (50k
#           cap → 422 BIZ-CAP; the export writes its own audit row) ·
#           BR-SHL-011 (q/sort/dir/page/per/f.‹name›) · BR-SHL-025 (server
#           enforces; UI gating is convenience)
# Tests:    06-backend/tests/test_us_aud_004_006_viewer.py (per-TC; RLS halves =
#           G5 isolation suite on live Postgres)
# Impacts:  config/urls.py (route registration) · FI-01 typed client (the 11b
#           §2.13 ratified rows) · every per-entity Audit tab (BR-AUD-010 reads
#           the same store through selectors.entity_trail)
# ───────────────────────────────────────────────────────
"""audit API endpoints — the ratified 11b §2.13 rows (A11 Addendum r2).

    GET  /audit-log          list + filters      (BR-AUD-009/013)
    GET  /audit-log/{id}     one row's drawer    (BR-AUD-009 drawer half)
    POST /audit-log/export   202 + job_id        (BR-AUD-014)

THIN by law (B8/LAW 0): reads go through selectors, the write (the export's own
audit row) goes through services, no ORM here. Refusals are catalog exceptions
rendered by the BE-02 handler.

**Read-only by construction (BR-AUD-002 / HR-4 / 11b G8).** The two row
resources define a `get` handler and nothing else, so POST/PUT/PATCH/DELETE
answer 405 from DRF's own dispatch — the refusal is structural, not a check
someone can forget to write. `POST /audit-log/export` is a different resource:
it creates an EXPORT JOB, never an audit row edit.

RBAC disposition (recorded, not silently chosen): **the A4 matrix has no
audit-log row at all** — its nine rows are Settings, Users, Plans & Rates,
Premises/Accounts, Reads & Billing, Payments, Approvals, Finance, Reports. The
role gate therefore comes from BR-AUD-009 (CONFIRMED — A1 S61 addendum): "read-
only; System Admin + Executive", which US-AUD-004 TC-4/TC-5 assert directly
(Executive reads; Billing Clerk is denied server-side). That is `AdminOrExecutive`
— the same class A4's Settings/Finance rows already produce. Export rides the
same pair: US-AUD-006 §1 casts a System Admin but names no narrower rule, and
A4 gives Executive "Full" on Finance/reconcile/export. Flagged for the PO batch
as a candidate A4 row ("Audit log — Full / — / Full") so the matrix stops being
silent on a screen that exists.

Window headers (Eng disposition, flagged): the response carries
`X-Audit-Window: hot|archive` and `X-Audit-Window-From` so a client can render
"showing the last 2 years" honestly instead of inferring it. The body stays the
plain BE-05 pagination envelope.
"""

from typing import Any

from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import selectors, services
from apps.identity.auth import IdentitySessionAuthentication
from core import errors, tenancy
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AdminOrExecutive, SystemAdminOnly


def _list_params(request: Any) -> Any:
    """BR-SHL-011 grammar with the BR-AUD-009 vocabulary. `q` is parsed and
    ignored on purpose: the A1 S61 design has NO free-text search — the entity
    type/id filter is the lookup path (EP-AUD-02 capability row)."""
    return parse_list_params(
        request.query_params,
        allowed_sorts=tuple(selectors.AUDIT_LIST_SORTS),
        default_sort=selectors.AUDIT_LIST_DEFAULT_SORT,
        allowed_filters=selectors.AUDIT_FILTERS,
    )


def _direction(request: Any, params: Any) -> str:
    """Capability-row default: When DESC (newest first); an explicit ?dir wins."""
    if "dir" in request.query_params:
        return params.dir
    if (params.sort or selectors.AUDIT_LIST_DEFAULT_SORT) == selectors.AUDIT_LIST_DEFAULT_SORT:
        return selectors.AUDIT_LIST_DEFAULT_DIR
    return params.dir


class AuditLogView(APIView):
    """GET /audit-log — S61's list. No other verb is defined here (BR-AUD-002)."""

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AdminOrExecutive]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        params = _list_params(request)
        archive = selectors.wants_archive(request.query_params)
        # US-AUD-008: with the opt-in ON this reads the hot table AND every
        # cold partition; OFF (the default) it never touches cold storage.
        queryset = selectors.audit_result_set(
            tenant_id,
            filters=params.filters,
            archive=archive,
            sort=params.sort,
            direction=_direction(request, params),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response(
            selectors.audit_page(
                tenant_id,
                list(page),
                archive=archive,
                # CR-089 wave C `C6` — an ENTITY-SCOPED read carries the recorded
                # values on the row, so a per-entity Audit tab shows what a value
                # WAS without a press. `f.entity_id` is what makes the page
                # bounded by one record; the unfiltered S61 list is unchanged.
                with_values=bool(params.filters.get("entity_id")),
            )
        )
        # BR-AUD-013 made visible: which window answered this query.
        response["X-Audit-Window"] = "archive" if archive else "hot"
        response["X-Audit-Window-From"] = selectors.window_floor(archive=archive).isoformat()
        return response


class AuditLogEntryView(APIView):
    """GET /audit-log/{id} — the US-AUD-005 drawer payload (who/what/when/
    entity/before/after). Read-only: no other verb is defined (BR-AUD-002)."""

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AdminOrExecutive]

    def get(self, request, entry_id):
        tenant_id = tenancy.require_tenant(request)
        row = selectors.audit_entry(tenant_id, entry_id)
        if row is None:
            # Absent OR another tenant's row — one body for both (HR-1/G4).
            raise errors.NotFoundError()
        names = selectors.actor_names(tenant_id, [row.actor_user_id])
        return Response(selectors.audit_detail(row, names))


class AuditEntryDiagnosticView(APIView):
    """GET /audit-log/{id}/diagnostic — **the reproduction record, System Admin only.**

    CR-067 task B2's missing half (`DEF-3321`). `error_diagnostics` has been
    written, referenced and swept since the A-tasks landed, and **nothing read it
    back**: this module defined three routes, none of them touched that table,
    and `apps/audit/diagnostic_models.py`'s own trailer said so —
    `D=deferred(no endpoint of its own)`. So the six lines CR-067 §5 measures the
    whole change against — the exception, where in the code, which job step,
    which release, the settings in force, the request's field names — could not
    reach any screen in this product. Hard-won law 2 one layer lower than usual:
    not a component nothing passes a prop to, a TABLE nothing serves.

    ⚠ **`SystemAdminOnly` HERE IS THE BOUNDARY, AND IT IS THE POINT OF THE
    ENDPOINT AS MUCH AS THE DATA IS.** Every other route in this module is
    `AdminOrExecutive` (BR-AUD-009 — *"read-only; System Admin + Executive"*),
    and the S61 drawer's own role check is `BR-SHL-025` CONVENIENCE: both halves
    of that drawer come out of the ONE payload `GET /audit-log/{id}` already
    serves, so `useTenantRole` decides what is DRAWN and an Executive holds the
    bytes either way. **A separate read is what turns that into a real gate:**
    the technical record now arrives on its own request, and an Executive asking
    for it is refused 403 AUTH-002 by the server with the BR-AUD-018 attempt row
    written, whatever the browser thinks. `DEF-3321`'s own prevention column asks
    for exactly this.

    ⚠ **WHY A NARROWER GATE THAN THE SCREEN IT SITS ON IS NOT A CONTRADICTION.**
    BR-AUD-009 says who may read the TRAIL — what was attempted, by whom, when,
    and the plain-words reason. This serves something else: frames, a release, a
    deployment's configuration. CR-067 §3's approved table already says *"a second
    section in the same row's drawer, **System Admin only**"*, so the narrowing is
    the change request's own, ratified with it, and not a choice made here.
    Reported for the BR-AUD-009 amendment alongside `f.outcome`.

    **Read-only by construction**, like every other row resource here: `get` is
    the only handler, so POST/PUT/PATCH/DELETE answer 405 from DRF's own dispatch
    (BR-AUD-002 / HR-4). There is no write path to a diagnostic at all — the
    kernel's sink is the only writer, and the sweep is the only remover.

    **NO `audit_log` ROW IS WRITTEN FOR A SUCCESSFUL READ**, which is hard rule 7
    read as it is written: the trail attaches to a MONEY action, and no read on
    this screen — including `GET /audit-log/{id}` itself — writes one. A REFUSED
    read is audited already, by the BE-02 handler's BR-AUD-018 attempt row, which
    is the half that matters for a System-Admin-only door.
    """

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def get(self, request, entry_id):
        tenant_id = tenancy.require_tenant(request)
        row = selectors.audit_entry(tenant_id, entry_id)
        if row is None:
            # Absent OR another tenant's row — ONE body for both (HR-1/G4), the
            # same answer `AuditLogEntryView` gives, so a caller cannot learn
            # that a reference exists somewhere else by the shape of the refusal.
            raise errors.NotFoundError()
        # A row whose detail has expired answers 200 with `held: false` and a
        # reason. It is a normal state, not a fault — see `selectors.audit_diagnostic`.
        return Response(selectors.audit_diagnostic(row))


class AuditLogExportView(APIView):
    """POST /audit-log/export — 202 + job_id (B12 r1 async contract)."""

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AdminOrExecutive]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        params = _list_params(request)
        # The export covers the caller's CURRENT filters (IS-9/BR-AUD-014).
        # They may arrive as query params (the S61 URL state, BR-SHL-011) or in
        # the body; the body wins where both name the same filter.
        filters = dict(params.filters)
        body = request.data if isinstance(request.data, dict) else {}
        body_filters = body.get("filters")
        if isinstance(body_filters, dict):
            filters.update(
                {
                    str(key): str(value)
                    for key, value in body_filters.items()
                    if key in selectors.AUDIT_FILTERS
                }
            )
        archive = selectors.wants_archive(request.query_params) or bool(body.get("archive"))
        accepted = services.request_export(
            actor=request.user, tenant_id=tenant_id, filters=filters, archive=archive
        )
        return Response(accepted, status=202)


class UserActivityAuditFeedView(APIView):
    """US-AUD-009 — the A14 Compliance card "User activity audit".

    GET  serves the feed DEFINITION (columns, parameters, formats), which is
         what the S44 catalog needs to route the card here rather than to the
         generic viewer (BR-AUD-017).
    POST runs it: 202 + job_id, through the same guarded, audited, capped
         pipeline as the S61 export.

    Same role gate as everything else in this module (BR-AUD-009) — a report
    over the audit dataset grants nothing the dataset itself does not.
    """

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AdminOrExecutive]

    def get(self, request):
        tenancy.require_tenant(request)
        return Response(services.feed_definition())

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        params = _list_params(request)
        body = request.data if isinstance(request.data, dict) else {}
        filters = dict(params.filters)
        body_filters = body.get("filters")
        if isinstance(body_filters, dict):
            filters.update(
                {
                    str(key): str(value)
                    for key, value in body_filters.items()
                    if key in selectors.AUDIT_FILTERS
                }
            )
        columns = body.get("columns")
        accepted = services.request_feed(
            actor=request.user,
            tenant_id=tenant_id,
            filters=filters,
            columns=list(columns) if isinstance(columns, list) else None,
            fmt=str(body.get("format") or "csv"),
        )
        return Response(accepted, status=202)


class RetentionRunsView(APIView):
    """GET /retention/runs — **has the retention job ever run, and what moved?**

    US-MET-020 / US-AUD-007's run record, reachable for the first time. Its
    `archive_job_runs` ledger has existed since audit migration 0004, is written
    on every run by `core.archival` through a registered recorder, and appeared
    in a migration, a management command and `core/archival.py` **and in no
    `api.py` anywhere**. An operator subject to a 7-year retention obligation
    could not answer the question at all.

    **READ-ONLY BY CONSTRUCTION, and here that is a rule rather than a habit.**
    BR-MET-055 and BR-AUD-012 both say archival is *"an AUTOMATIC scheduled job
    … never manual"*, and `core.archival.run_archival` refuses any caller
    without the scheduler token `manage.py archive_partitions` holds. This class
    defines `get` and nothing else, so POST/PUT/PATCH/DELETE answer 405 from
    DRF's own dispatch — the same structural refusal `AuditLogView` relies on
    (BR-AUD-002 / HR-4). Making the job triggerable from here would be building
    exactly the product path both rules forbid.

    ROLE GATE: the same `AdminOrExecutive` the rest of this module carries
    (BR-AUD-009). Retention is a compliance read over the same store.

    ⚠ **`archive_job_runs` HAS NO `tenant_id` AND NO RLS POLICY** — a partition
    is shared across tenants, so a run belongs to none of them. The selector
    REDACTS each entry's tenant list to a single "were my rows in this one?"
    boolean before it leaves the module; nothing here serves the raw payload,
    because on this one table RLS has no policy to catch a leak with.
    """

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AdminOrExecutive]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        table = request.query_params.get("table") or None
        if table is not None and table not in selectors.archival.ARCHIVED_TABLES:
            # An unknown table name is IGNORED rather than 4xx'd, exactly as an
            # undeclared `f.` param is on every list here (BE-05) — a filter is
            # never the thing that breaks a compliance read.
            table = None
        return Response(
            {
                "status": selectors.archive_status(tenant_id),
                "runs": selectors.archive_run_list(tenant_id, table=table),
            }
        )


urlpatterns = [
    path("audit-log", AuditLogView.as_view()),
    path("retention/runs", RetentionRunsView.as_view()),
    path("reports/user-activity-audit", UserActivityAuditFeedView.as_view()),
    path("audit-log/export", AuditLogExportView.as_view()),  # before the {id} row
    path("audit-log/<uuid:entry_id>", AuditLogEntryView.as_view()),
    # CR-067 B2 / DEF-3321 — nested under the row it belongs to, because the row
    # is what 404s (see `selectors.audit_diagnostic` for why that matters).
    path("audit-log/<uuid:entry_id>/diagnostic", AuditEntryDiagnosticView.as_view()),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-004@009e809 (EP-AUD-02 lead story; also US-AUD-005@009e809 · US-AUD-006@009e809 — hash = sha256/7 of the source epic)
# packet: US-AUD-009@6b3d915 (EP-AUD-03 feed story — the user-activity-audit route, added 2026-08-15)
# generated: 2026-08-09 by story-coder v1 (API-gap lane — the ratified 11b §2.13 rows, never built)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S61 is a later lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ py_compile✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row; G9 active on this file: catalog exceptions only, no ORM) · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: [US-AUD-009 lane 2026-08-15] the feed's route string `/reports/user-activity-audit` follows no 11b row — the reports contract rows are S44/S45/S46's and this card is OWNED here by pack assignment; REPORTED for the A11 addendum alongside the reads endpoints · the compliance PDF half of US-AUD-009 §1 is NOT built and NOT stubbed: no module in this codebase renders a PDF, so feed_definition() declares pdf:false with the reason and a PDF request is refused · RBAC comes from BR-AUD-009 (System Admin + Executive), NOT from A4 — the A4 matrix has no audit-log row; disposition documented in the module docstring and flagged for the PO batch as a candidate A4 row · BR-AUD-009's module filter + BR-AUD-004's action-type class filter are absent (they need the unbuilt US-AUD-002 event-code catalog — REPORTED, not invented; `f.action` filters the code) · Source column + drawer request metadata served null (GAP AUD-D2, no B2 column) · `archive=true` widens to the BR-AUD-012 7-year floor inside the SAME store; cold-storage search is US-AUD-008 (W5, not built) · X-Audit-Window/-From response headers are Eng mechanics (no contract row names them) — flagged · POST /audit-log/export enqueues through core.jobs, which has NO registered store on this deployment: it fails loudly rather than answering a 202 with no job record behind it (same posture as apps/rating POST /rate-changes) — REPORTED · no PUT/PATCH/DELETE handler exists on either row resource, so the 405 is structural (BR-AUD-002/HR-4/11b G8) and is asserted by test_us_aud_004_tc7
# exceptions: [retention-surface lane 2026-08-16] `GET /retention/runs` follows
#         no 11b row — the contract has no retention entry — so it uses the
#         house grammar and is REPORTED for the A11 addendum alongside the reads
#         endpoints. THREE things stated rather than assumed: (1) it is a READ
#         and creates no manual trigger — BR-MET-055/BR-AUD-012 forbid a product
#         path to archival and `run_archival` still refuses any caller without
#         the scheduler token, so the class defines `get` alone and every other
#         verb 405s structurally; (2) `archive_job_runs` carries NO tenant_id
#         and NO RLS policy, so the selector REDACTS each entry's `tenants` list
#         to one boolean before it leaves the module — on this table RLS has no
#         policy to catch a leak with, and serving the raw payload would have
#         been a cross-tenant disclosure; (3) the run rows are PLATFORM events
#         and every tenant sees the same history, which is correct because the
#         runs are platform-wide and hiding a month's retention from a tenant
#         whose rows were in it would make the compliance answer wrong · the
#         list is NOT paginated: at most one row per table per month, so seven
#         years of a two-table obligation is under 200 rows and BR-AUD-013's
#         no-unbounded rule is about `audit_log`, which grows by the million
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
