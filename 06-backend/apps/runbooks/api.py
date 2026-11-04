# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-003 · US-RBS-018 (EP-RBS-01) — CR-075 wave D task D1:
#           07-endpoints.md rows 1, 2, 4, 8, 9, 10, 11 and 14 — the eight READ
#           routes the three surfaces need. Screens: RBS-001 · RBS-002 ·
#           RBS-003 · RBS-006 · RBS-008
# Rules:    CLAUDE.md hard rule 1 (the read runs under the request's tenant
#           context; another tenant's run is a 404 identical to an absent one) ·
#           NFR-3 (universal server pagination, `per` clamped
#           50/100/200/500/1000, default 50) · NFR-5 (no hard caps anywhere) ·
#           BR-RBS-020 (the report is composed at close and FROZEN — served
#           byte-identical, never recomposed) · BR-RBS-002 (a Check is
#           CONSTRUCTED with no writer; nothing here writes a domain row) ·
#           BR-RBS-025 (a category with no template is never drawn as a
#           filter) · BR-RBS-039 (no foreign read outside apps/runbooks/seams/)
#           · B14 rule 31 (no database id is ever the visible value of a field)
#           · B8 / LAW 0 (thin: resolve the tenant, call the module, answer —
#           no ORM here, G6 rule 5)
# Tests:    06-backend/tests/test_us_rbs_003_endpoints.py (the eight routes,
#           the clamp, the frozen report, the two files, the cross-tenant 404) ·
#           06-backend/tests/test_us_rbs_003_pg.py (TC-RBS-7's shape at the
#           ENDPOINT: a second tenant sees none of the first tenant's runs,
#           under the non-superuser probe role, on real PostgreSQL)
# Impacts:  06-backend/config/urls.py (one include line — and it is what turns
#           `G27 engine-surface` green for this module) ·
#           10-scripts/gates/g74_unread_tables_baseline.txt (RunbookRunRecord
#           and WorkItem get their first reader here) ·
#           10-scripts/render-checks/rbs-d-endpoints.mjs
# ───────────────────────────────────────────────────────
"""The runbooks module's first door — eight READ routes, and not one writer.

**`apps/runbooks` had no `api.py`, no `urls.py`, and nothing in `config/urls.py`
reaching it.** 4,369 lines of engine behind no address at all, which `G27
engine-surface` reported as *"an entire module is invisible — nothing it does
can be triggered, listed or audited through the product"*. That red was
sanctioned and dated in `12-governance/02-decision-log.md` §15, which refused a
fake route to clear it and named what would: *"`G27` goes green for this module
the moment `config/urls.py` reaches one real runbooks route. That is wave D."*
This file is that, and the paragraph holding the red is deleted in the same
commit — a hold that outlives its condition is `DEF-CWP-3925`'s mirror defect.

THE EIGHT, AND WHAT EACH ANSWERS
---------------------------------
    GET runbooks                          the catalogue: this tenant's runbooks,
                                          each with its last run and its open
                                          items; filter kind · category
    GET runbooks/templates                the shipped library, with **Added ·
                                          Not added** per tenant and the chips
                                          built from the templates PRESENT
    GET runbooks/runs                     history across every runbook, newest
                                          first; filter runbook · category ·
                                          kind · outcome · date
    GET runbooks/runs/{id}                one run: header, counts, status,
                                          approver
    GET runbooks/runs/{id}/report         **the frozen block list, unchanged**
    GET runbooks/runs/{id}/records        per-record plan and outcome; filter
                                          outcome
    GET runbooks/runs/{id}/results/done.csv
    GET runbooks/runs/{id}/results/not-done.csv
                                          the two result files, each row
                                          carrying its reason and its fix
    GET runbooks/{key}                    one runbook: definition, schedule,
                                          cap, guards, next run

⚠ **THE ORDER OF `urlpatterns` IS LOAD-BEARING AND IT IS NOT A MATTER OF
TASTE.** `runbooks/<str:key>` matches the literal path `runbooks/templates`, so
a library request would resolve to *"the runbook whose key is templates"* and
answer 404. That is not hypothetical: `config/urls.py` records
`integrations/subprocessors` doing exactly this — read as a provider key and
answered **405 Method Not Allowed** — under a comment that had asserted the
collision away. Hard-won law 1, and *it was the browser that found it, not the
reasoning*. So every literal path is registered BEFORE the key pattern, and
`tests/test_us_rbs_003_endpoints.py` RESOLVES each of the eight through
`config/urls.py` rather than trusting this paragraph.

THE THREE WRITES, ADDED BY WAVE E — AND WHAT THEY DO NOT TOUCH
---------------------------------------------------------------
    POST runbooks                         add a shipped template to My runbooks
    POST runbooks/{key}/clone             clone and vary (`RB-040`)
    PUT  runbooks/{key}                   schedule · cap · gate · enabled ·
                                          visibility — **writes a new version**

⚠ **THIS FILE'S DOCSTRING SAID *"NOTHING HERE WRITES ANYTHING"* UNTIL WAVE E,
AND IT WAS TRUE THEN.** It is corrected here rather than left standing, because
a comment claiming a guarantee is hard-won law 1's whole subject and the next
reader would have taken it for the module's promise. **What has NOT changed is
the promise itself**: `BR-RBS-002` — a Check is CONSTRUCTED with no ports — is
what lets two people press **Run ▶** on a thousand accounts, and phase 1's
launch sentence is *"nothing can be written: no writer is bound"*. The three
routes above write **this module's own two tables and nothing else's**: a
runbook row and a version row. No port is bound, nothing outside
`apps/runbooks` is written, and `kind` is in `services.FROZEN_FIELDS` so there
is no path from an edit to turning a Check into an Action.

**Still waves L and beyond:** `…/runs`, `…/approve`, `…/stop`, `…/decide`,
`…/work-items`. `07-endpoints.md`'s six refusal keys belong with those routes —
a `message_key` is minted in all eleven catalogues in the same commit as its
raise site, or it reaches a clerk as **silence** (PO ruling 2026-08-19,
`core/refusal_catalogue.py`). **This file raises none of the six**, so it mints
none of the six. It raises four of its own — `already_added`,
`unknown_template`, `not_editable`, `update_pending` — and a fifth,
`dry_run_first`, is raised by `services.open_run`; all five are in all eleven
catalogues in this commit.

⚠ **AND IT COMPOSES NO IDEMPOTENCY KEY.** `OQ-RBS-1737` is OPEN — how
`runbook_run_records.idempotency_key` is composed contradicts itself across our
own documents (`DEF-RBS-4246`) and the cost of guessing is *496 notices instead
of 248, and no test that can see it*. Nothing below writes a record, so nothing
below needs one; the CSV routes READ the column's row and never mint a value.
"""

from typing import Any

from django.http import StreamingHttpResponse
from django.urls import path, re_path
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

from apps.runbooks import cutover, domains, result_files, selectors, services
from core import errors
from core.pagination import parse_list_params
from core.permissions import ROLES, SYSTEM_ADMIN, AnyTenantRole, RoleRequired
from core.tenancy import require_tenant, stream_within_tenant_context

#: `07-endpoints.md` §1 and §2: **Staff reads; Admin writes.** Every route here
#: is a read, so all three tenant roles may call every one of them. The Admin
#: half of that sentence arrives with the write routes in waves E and L, and it
#: will be a narrower permission class on those views — never an `if` inside one
#: of these (`SettingsReadAnyWriteSystemAdmin`'s own docstring is the precedent,
#: and `DEF-196` is what happens when a read and a write share one gate).
#:
#: ⚠ **ROLE VISIBILITY BY CATEGORY IS `D5`, NOT THIS TASK** (`RB-050`,
#: `BR-RBS-024`: a Finance user's library shows Finance, Payments and
#: Collections and not Platform). It is a FILTER on what a signed-in staff
#: member sees, not a different answer to *may you call this* — so it lands as a
#: predicate inside the selectors, and this class does not pretend to enforce it
#: today. Stated rather than left to be discovered, because a reader could take
#: `AnyTenantRole` for the whole of the access rule.
READ_ROLES = AnyTenantRole


class ReadAnyRoleWriteSystemAdmin(RoleRequired):
    """**Staff reads; Admin writes** — `07-endpoints.md` §1, in one class.

    Two of this module's routes answer both verbs on one address, because Django
    takes the first pattern that matches and `runbooks` cannot be two views:
    `GET · POST /runbooks` and `GET · PUT /runbooks/{key}`.

    ⚠ **IT IS NOT `SettingsReadAnyWriteSystemAdmin`, AND THE DIFFERENCE IS A
    SIGNED MATRIX RATHER THAN A PREFERENCE.** That class reads
    `{system_admin, executive}` because `A4`'s `settings_lookups` row gives a
    Billing Clerk **no cell at all** — and reusing it here would take the
    runbooks catalogue away from the very role that runs the utility day to day.
    `07-endpoints.md` §1 says *Staff reads*, all three roles, which is
    `AnyTenantRole`'s set. `DEF-SHL-4272` is what the other mistake costs: a
    clerk could not use the product **at all for sixteen days** because a screen
    the shell needs was served under the settings class.

    ⚠ **AND THE OBVIOUS FIX THERE IS THE WRONG ONE HERE TOO.** Widening
    `SettingsReadAnyWriteSystemAdmin` to all three roles re-opens `DEF-196`;
    that class's own docstring records the first cut of that fix sailing past
    every new test and being caught by a story case. So this is a NEW class in
    the module that needs it, exactly as `ShellDisplayRead` was.

    ⚠ **A READ GATE PLUS A WRITE GATE, NEVER A BRANCH INSIDE A VIEW.** `DEF-196`
    is what happens when a read and a write share one `if`. The rule is one
    sentence and it lives in one place where it can be read, tested and cited.
    """

    allowed_roles = ROLES
    #: Verbs that mutate nothing.
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def has_permission(self, request: Any, view: Any) -> bool:
        role = getattr(request, "tenant_role", None)
        if role not in ROLES or not getattr(
            getattr(request, "user", None), "is_authenticated", False
        ):
            return False  # 401 / 403, rendered by the shared handler
        if request.method in self.SAFE_METHODS:
            return role in self.allowed_roles
        return role == SYSTEM_ADMIN


class SystemAdminWrite(RoleRequired):
    """`POST /runbooks/{key}/clone` — Admin, and no read to widen (`07-endpoints.md` row 6)."""

    allowed_roles = frozenset({SYSTEM_ADMIN})


def _envelope(request: Any, result: dict[str, Any]) -> dict[str, Any]:
    """A selector's page dict → **the four keys this product puts on the wire**.

    In goes `{rows, page, per, total}`; out goes `{count, next, previous,
    results}` and nothing else. `07-frontend/src/api/paginated.ts` is the ONE
    description of those four names on the client and `G114` fails a second one.

    ⚠ **THE NAMES CHANGE HERE AND THAT IS WHY THREE SHIPPED SCREENS DREW EMPTY
    TABLES** (`DEF-WRK-4119`, `DEF-AST-4120`, 2026-09-05). `rows` → `results`,
    `total` → `count`. A client that says `rows` is reading the SELECTOR, not
    the API — which is the right file for the row shape and the wrong one for
    the reply.

    ⚠ **AND EVERY OTHER KEY IS DISCARDED.** This returns a fresh dict; it does
    not update `result`. A view with an extra figure must spread —
    `{**_envelope(request, result), "category_chips": …}` — and
    `asset_work_orders` did not, so `maintenance_index` never left the server.
    `templates` below spreads for exactly this reason.
    """
    per, page, total = result["per"], result["page"], result["total"]
    last = max(1, -(-total // per))
    url = request.build_absolute_uri()
    return {
        "count": total,
        "next": replace_query_param(url, "page", page + 1) if page < last else None,
        "previous": replace_query_param(url, "page", page - 1) if page > 1 else None,
        "results": result["rows"],
    }


def _actor_id(request: Any) -> Any:
    """The signed-in user's id, from the SESSION and never from client input.

    It becomes `runbook_versions.changed_by` — the *By* column of `RBS-004.7`,
    which is the tab an auditor asks for first. B12 §6a's service shape, and the
    same helper every other module's `api.py` writes for the same reason.
    """
    user = getattr(request, "user", None)
    return getattr(user, "id", None) or getattr(user, "pk", None)


def _payload(request: Any) -> dict[str, Any]:
    """The request body as a dict, or a refusal in the envelope.

    A list or a string reaching a service that does `payload.get(...)` is an
    `AttributeError` in a 500, so it is refused at the door in the B12 §3
    envelope instead — copied from `apps/work/api.py`, which learnt it the same
    way.
    """
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT)
    return data


def _filter(request: Any, name: str) -> str | None:
    """One declared filter, in `BR-SHL-011`'s `f.<name>` grammar.

    An unknown VALUE falls through to the selector, which ignores anything
    outside its own vocabulary — `f.outcome=purple` returns the unfiltered list
    rather than a 400, because a list URL can never 4xx over its params.
    """
    value = request.query_params.get(f"f.{name}")
    return value.strip() if isinstance(value, str) and value.strip() else None


class CsvRenderer(BaseRenderer):
    """Passthrough renderer so a CSV route can ANSWER `Accept: text/csv`.

    `@api_view`'s default renderers satisfy only JSON, so DRF's content
    negotiation refuses a browser's `Accept: text/csv` with **400 before the
    view ever runs** — `DEF-553`, which is why S28's template button had never
    downloaded anything. The two CSV views return an `HttpResponse` and never
    call `render`; this class exists so the negotiation step has a renderer
    whose media type matches. Copied deliberately from
    `apps/metering/api.py::CsvRenderer` rather than shared: a renderer is four
    lines and a cross-module import for it would be a coupling `G115` is right
    to refuse.
    """

    media_type = "text/csv"
    format = "csv"

    def render(
        self, data: Any, accepted_media_type: Any = None, renderer_context: Any = None
    ) -> Any:
        return data


# ── the catalogue and the library ────────────────────────────────────────────


@api_view(["GET", "POST"])
@permission_classes([ReadAnyRoleWriteSystemAdmin])
def runbooks_list(request: Any) -> Response:
    """`GET /runbooks` — row 1 · `POST /runbooks` — row 5. One address, two verbs.

    **GET** serves `RBS-001` (Runbooks home) and `RBS-003` (My runbooks). Pages
    server-side with `per` clamped 50/100/200/500/1000, default 50 (`NFR-3`),
    and carries no per-tenant maximum of any kind (`NFR-5`) — a tenant with four
    hundred cloned runbooks gets four hundred, fifty at a time. From wave `D5`
    it is narrowed by **role visibility** (`RB-050`, `BR-RBS-024` clause 2):
    what a signed-in staff member is SHOWN, never what they may call.

    **POST** adds a shipped template to My runbooks — `07-endpoints.md` row 5,
    body `{template_key}`, **Admin**, `201 · the new runbook`. `BR-RBS-043`:
    add once, then clone; a second add is refused rather than answered `201`
    over a row that already existed.

    ⚠ **`POST` LANDS ON THIS FUNCTION BECAUSE DJANGO TAKES THE FIRST PATTERN
    THAT MATCHES AND `runbooks` IS ONE ADDRESS.** A second view mounted on the
    same path would never be reached — which is `integrations/subprocessors`'
    defect wearing a different hat. The permission split is in the class, never
    in an `if` here (`DEF-196`).
    """
    tenant_id = require_tenant(request)
    if request.method == "POST":
        runbook = services.add_template(
            tenant_id,
            str(_payload(request).get("template_key") or ""),
            actor_id=_actor_id(request),
        )
        return Response(selectors.runbook_detail(tenant_id, runbook.key), status=201)
    params = parse_list_params(
        request.query_params, allowed_sorts=(), default_sort=None, allowed_filters=()
    )
    result = selectors.catalogue_page(
        tenant_id,
        kind=_filter(request, "kind"),
        category=_filter(request, "category"),
        q=params.q,
        role=getattr(request, "tenant_role", None),
        page=params.page,
        per=params.per,
    )
    return Response(_envelope(request, result))


@api_view(["POST"])
@permission_classes([SystemAdminWrite])
def runbook_runs(request: Any, key: str) -> Response:
    """`POST /runbooks/{key}/runs` — row 4: a run started by a person (`CR-173-BRC10`).

    Body `{mode: "dry" | "live", parameters?: {name: value}}`. **Admin** ·
    `202 · {job_id, status_url}`. The run rides the schedule's own job kinds
    and body, so `open_run`'s two refusals hold for it unchanged; `services.
    request_run` adds the three that belong to a person's request.

    ⚠ **REGISTERED BEFORE `runbooks/<str:key>`** — *literals first*, as every
    other route in this file.
    """
    from core import jobs as core_jobs

    tenant_id = require_tenant(request)
    runbook = selectors.runbook_by_key(tenant_id, key)
    if runbook is None:
        raise errors.NotFoundError()
    body = _payload(request)
    user = getattr(request, "user", None)
    name = ""
    for attribute in ("full_name", "email"):
        name = str(getattr(user, attribute, "") or "").strip()
        if name:
            break
    record = services.request_run(
        runbook,
        mode=str(body.get("mode") or "dry"),
        parameters=body.get("parameters") if isinstance(body.get("parameters"), dict) else {},
        started_by_name=name or None,
    )
    return Response(core_jobs.accepted(record), status=202)


@api_view(["GET"])
@permission_classes([READ_ROLES])
def runbook_templates(request: Any) -> Response:
    """`GET /runbooks/templates` — row 4: the shipped library, per tenant.

    `RBS-002`. Each row says **Added** or **Not added** for THIS tenant, and
    `category_chips` is built from the templates PRESENT and never from the
    fixed sixteen (`BR-RBS-025`, `TC-RBS-20`) — a chip that filters to nothing
    is dead UI (hard-won law 2).

    ⚠ **THE CHIPS ARE SPREAD ONTO THE ENVELOPE, NOT RETURNED BESIDE IT.**
    `_envelope` builds a fresh dict and discards every other key; a view with an
    extra figure that hands its whole result to it loses that figure silently,
    which is exactly how `maintenance_index` never left the server
    (`DEF-AST-4120`).
    """
    tenant_id = require_tenant(request)
    params = parse_list_params(
        request.query_params, allowed_sorts=(), default_sort=None, allowed_filters=()
    )
    result = selectors.templates_page(
        tenant_id,
        kind=_filter(request, "kind"),
        category=_filter(request, "category"),
        q=params.q,
        role=getattr(request, "tenant_role", None),
        page=params.page,
        per=params.per,
    )
    return Response(
        {
            **_envelope(request, result),
            "category_chips": result["category_chips"],
            "kind_chips": result["kind_chips"],
        }
    )


# ── the run surfaces ─────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([READ_ROLES])
def runs_list(request: Any) -> Response:
    """`GET /runbooks/runs` — row 8: history across runbooks, newest first.

    `RBS-008`. Filters are `BR-SHL-011`'s `f.<name>` grammar: `f.runbook`,
    `f.category`, `f.kind`, `f.outcome`, `f.from`, `f.to`. An unknown filter
    name is IGNORED and an unknown value falls back to unfiltered — a list URL
    never 4xx's over its own params.
    """
    tenant_id = require_tenant(request)
    params = parse_list_params(
        request.query_params, allowed_sorts=(), default_sort=None, allowed_filters=()
    )
    result = selectors.runs_page(
        tenant_id,
        runbook_key=_filter(request, "runbook"),
        category=_filter(request, "category"),
        kind=_filter(request, "kind"),
        outcome=_filter(request, "outcome"),
        started_from=_filter(request, "from"),
        started_to=_filter(request, "to"),
        q=params.q,
        page=params.page,
        per=params.per,
    )
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([READ_ROLES])
def run_detail(request: Any, run_id: str) -> Response:
    """`GET /runbooks/runs/{id}` — row 9: header, counts, status, approver.

    ⚠ **A RUN OF ANOTHER TENANT AND A RUN THAT NEVER EXISTED ANSWER THE SAME
    404** (`HR-1`, hard rule 1). The read is filtered by tenant BEFORE the id is
    looked at, so neither the status nor the body can be used to ask whether a
    given run id is real somewhere else in the product.
    """
    tenant_id = require_tenant(request)
    found = selectors.run_header(tenant_id, run_id)
    if found is None:
        raise errors.NotFoundError()
    return Response(found)


@api_view(["GET"])
@permission_classes([READ_ROLES])
def run_report(request: Any, run_id: str) -> Response:
    """`GET /runbooks/runs/{id}/report` — row 10: **the frozen block list**.

    `BR-RBS-020`: *a run's report is composed once, at CLOSE, from the twelve
    block types, and frozen; a later code change never alters a past result.*
    This route reads `runbook_runs.report` and answers it. It does not call the
    runbook's `report()`, does not re-derive a block, does not reshape a
    payload, does not add a field a newer renderer wants and does not drop one
    it no longer draws.

    ⚠ **`07-endpoints.md` E-5 NAMES THIS ROUTE AS THE PLACE THE MISTAKE GETS
    MADE:** *"a build lane that renders from the live definition instead passes
    every test until a runbook is edited, and then rewrites history."* It passes
    every test because a fresh fixture's live report and its frozen one are
    identical; the difference appears only after an edit, which no fixture
    performs by accident. `TC-RBS-16` is the assertion, and this wave's version
    of it re-reads the route TWICE and compares the two response bodies BYTE FOR
    BYTE.

    ⚠ **AND IT MATTERS TODAY, NOT ONLY AFTER AN EDIT.** `DEF-RBS-4284` is open:
    the engine's six payloads and the wave-C renderer's six types disagree, and
    the fix moves the ENGINE onto the renderer's shapes. A run closed before
    that lands is frozen in the old shape and one closed after it in the new,
    **and both are correct** — the report is what was composed that day. A
    serializer that "helped" by translating between them would rewrite the first
    result this product ever produced.

    The body is `{"blocks": [...]}` rather than a bare array: a top-level JSON
    array cannot be extended without breaking every reader, and a run that
    failed at close legitimately has **no** blocks — `{"blocks": []}` says that,
    where a bare `[]` and a missing response read the same.
    """
    tenant_id = require_tenant(request)
    blocks = selectors.run_report(tenant_id, run_id)
    if blocks is None:
        raise errors.NotFoundError()
    return Response({"blocks": blocks})


@api_view(["GET"])
@permission_classes([READ_ROLES])
def run_records(request: Any, run_id: str) -> Response:
    """`GET /runbooks/runs/{id}/records` — row 11: the plan and the outcome.

    Filter with `f.outcome`. Paged like every other list here; a volume runbook
    writes a record row only for what it acted on or flagged and a COUNT per
    outcome for the rest (`BR-RBS-035`), so this list and the run's `counts`
    answer two different questions and a screen needs both.
    """
    tenant_id = require_tenant(request)
    params = parse_list_params(
        request.query_params, allowed_sorts=(), default_sort=None, allowed_filters=()
    )
    result = selectors.run_records_page(
        tenant_id,
        run_id,
        outcome=_filter(request, "outcome"),
        page=params.page,
        per=params.per,
    )
    if result is None:
        raise errors.NotFoundError()
    return Response(_envelope(request, result))


@api_view(["GET"])
@permission_classes([READ_ROLES])
@renderer_classes([CsvRenderer, JSONRenderer])
def run_result_file(request: Any, run_id: str, outcome: str) -> Any:
    """`GET …/runs/{id}/results/{done|not-done}.csv` — row 14: the two files.

    *Each row carrying its reason and its fix* — `07-endpoints.md` row 14, and
    `BR-RBS-011` is why the fix column is not optional: **a failure with no
    route is a defect in the runbook**, because a finding a clerk cannot act on
    is a finding we should not have shown them.

    ⚠ **IT STREAMS, AND THAT IS THE `NFR-3`/`NFR-5` ANSWER FOR A DOWNLOAD.** A
    file with a page 2 is not a file, so this is the one read in the module that
    is deliberately not paged — which is precisely the shape `DEF-PAY-4221`
    describes (`GET /outstandings`, unpaginated *"ON PURPOSE … at a utility
    under 3,000 connections"*). The difference is that nothing is materialised:
    `StreamingHttpResponse` pulls the queryset with an iterator and the peak
    memory is one row, whatever the tenant's size. There is no cap on how many
    rows the file may carry — only on how many are in memory at once, which is
    what `NFR-5` asks for and what an unpaginated `list(...)` does not give.

    ⛔ **`stream_within_tenant_context` IS NOT DECORATION — `DEF-RBS-4296`, AND
    IT IS `DEF-2734` A SECOND TIME.** A `StreamingHttpResponse` returns from the
    view with its body UNCONSUMED. `TenantContextMiddleware` clears
    `app.tenant_id` in its `finally` the moment the view returns, and the WSGI
    server iterates the body afterwards — so the generator's first query runs
    with **no tenant marker**, the RLS policy's
    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL,
    `tenant_id = NULL` is not TRUE, and the queryset yields **zero rows**.
    Nothing raises. The download succeeds with a 200. **The file is a header and
    nothing under it**, which reads as *"the run did nothing"* — the most
    dangerous shape this product has.

    It was written without the wrapper here and the whole SQLite suite was green
    over it, because SQLite has no row-level security at all (hard-won law 14).
    `tests/test_us_rbs_003_pg.py` caught it on the first PostgreSQL run, and the
    case it caught it with asserts a NAMED ROW is in the body rather than
    asserting a status — a status assertion passes on an empty file.

    A run of another tenant and a run that never existed are the same 404.
    """
    tenant_id = require_tenant(request)
    if selectors.run_header(tenant_id, run_id) is None:
        raise errors.NotFoundError()
    done = outcome == "done"
    rows = selectors.run_result_records(tenant_id, run_id, done=done)
    response = StreamingHttpResponse(
        stream_within_tenant_context(tenant_id, result_files.stream(rows)),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{result_files.name(run_id, done)}"'
    return response


@api_view(["POST"])
@permission_classes([SystemAdminWrite])
def runbook_clone(request: Any, key: str) -> Response:
    """`POST /runbooks/{key}/clone` — row 6: clone and vary (`RB-040`).

    Body `{name}`; the copy carries `origin = cloned` and **its own version 1**.
    **Admin** · `201 · the copy`. This is wave E's goal sentence: *Tom clones
    Dunning, names it Commercial accounts, sets the first reminder to 15 days —
    both rows appear with their own schedule, cap and dry run, the Activity tab
    names him and the time, and the previous run still reads v3 with its report
    unchanged.*

    ⚠ **THE SOURCE'S OWN RUN HISTORY IS NOT COPIED, AND THAT IS THE SECOND HALF
    OF THE GOAL SENTENCE.** *The previous run still reads v3 with its report
    unchanged* is a fact about the SOURCE, which this route does not touch at
    all: no version of the source is written, no run of the source is altered,
    and `runbook_versions` is append-only in the database from `migrations/0003`
    so a later lane cannot do it by accident either.

    ⚠ **REGISTERED BEFORE `runbooks/<str:key>`, LIKE EVERY OTHER LITERAL.** It is
    three segments and out of collision range with the two-segment key pattern,
    but the ordering rule in this file is *literals first* without exceptions —
    an exception is what a later lane copies.

    A runbook of another tenant and one that never existed are the same 404
    (`HR-1`): the lookup is filtered by tenant before the key is looked at.
    """
    tenant_id = require_tenant(request)
    source = selectors.runbook_by_key(tenant_id, key)
    if source is None:
        raise errors.NotFoundError()
    copy = services.clone_runbook(
        source, name=str(_payload(request).get("name") or ""), actor_id=_actor_id(request)
    )
    return Response(selectors.runbook_detail(tenant_id, copy.key), status=201)


@api_view(["GET"])
@permission_classes([READ_ROLES])
def runbook_parameter_domain(request: Any, key: str, parameter: str) -> Response:
    """`GET /runbooks/{key}/domains/{parameter}` — what this tenant may choose.

    `BR-RBS-042` clause 2, PO verbatim 2026-09-06: *"every utility will not have
    all utility services or all combinations of Plans and rates, so we ahve to
    work in variables"*. **A two-service utility's *Services* list offers two.**

    ⚠ **IT PAGES, AND THE REASON IS THE `account` DOMAIN RATHER THAN THIS
    WAVE'S OWN DEMONSTRATION.** `service` is bounded by an eleven-row platform
    catalogue and would fit in one response for ever; `account` is **40,000 at
    the top of T5** with no ceiling above it (`NFR-5`). CLAUDE.md's opening
    paragraph names four shipped lists that are unpaginated *"on purpose"*
    because a utility under 3,000 connections could carry it — correct at T7 and
    13× short of T5 (`DEF-PAY-4221`). A picker endpoint that paged for one
    domain and not another would also be a client that has to know which is
    which, so it pages for both.

    ⚠ **AN EMPTY DOMAIN IS A 200 WITH ZERO ROWS, NEVER A 404 AND NEVER AN
    ERROR** (`TC-RBS-039.3`). A utility that has enabled no services yet is a
    utility mid-setup, not a bad request; the screen draws a sentence rather
    than an empty dropdown, which reads as broken.

    ⚠ **A PARAMETER WITH NO DOMAIN IS A 404 AND NOT AN EMPTY LIST.** *There is
    no list behind this input* and *this input's list is empty* are different
    facts, and a screen that could not tell them apart would draw *"you have not
    set any services up yet"* over a money box.

    A runbook of another tenant and one that never existed are the same 404
    (`HR-1`), like every other read in this file.
    """
    tenant_id = require_tenant(request)
    runbook = selectors.runbook_by_key(tenant_id, key)
    if runbook is None:
        raise errors.NotFoundError()
    definition = services.definition_for(runbook)
    declared = {p.name: p for p in (definition.parameters if definition else ())}
    found = declared.get(parameter)
    if found is None or found.domain is None:
        raise errors.NotFoundError()
    params = parse_list_params(
        request.query_params, allowed_sorts=(), default_sort=None, allowed_filters=()
    )
    return Response(
        _envelope(
            request,
            domains.page(found.domain, q=params.q or "", page=params.page, per=params.per),
        )
    )


@api_view(["GET", "PUT"])
@permission_classes([ReadAnyRoleWriteSystemAdmin])
def runbook_detail(request: Any, key: str) -> Response:
    """`GET /runbooks/{key}` — row 2 · `PUT /runbooks/{key}` — row 3.

    `RBS-004.1`, the setup renderer's head.

    ⚠ **REGISTERED LAST, AND THAT IS WHAT KEEPS `runbooks/templates` AND
    `runbooks/runs` REACHABLE.** `<str:key>` matches either of those literals,
    and Django takes the FIRST pattern that matches. `integrations/subprocessors`
    is the same collision, shipped: read as a provider key and answered 405
    under a comment asserting it could not happen. The tests resolve all eight
    paths through `config/urls.py` so the ordering is asserted rather than
    reasoned about.

    ⚠ **`schedule.next_run` IS `null` AND IT IS NOT A PLACEHOLDER.** Nothing in
    this product schedules a runbook yet: this module registers no job with the
    platform runner and `runbooks` carries no `next_run_at` column. `cron` and
    `timezone` travel as DECLARED so `RBS-004.3` can draw *"Nightly at 02:00,
    America/Chicago"* from the declaration itself; a computed next occurrence
    would be this module answering a question no part of it can yet act on, and
    `RB-022`'s rule runs both ways — a **Run ▶** a screen offers must actually
    run, and a schedule a screen displays must actually fire.

    ⚠ **`RBS-004.6`'s RUNS TAB IS `GET /runbooks/runs?f.runbook={key}`, NOT A
    SECOND PAGE ON THIS ROUTE.** `07-frontend/src/api/runbooksEndpoints.ts`
    (wave C task `C3`, written before this endpoint existed) calls
    `/runbooks/{key}?runs_page=&runs_per=` and says in its own docstring that it
    is *"a claim on `D1`"* to be settled with one mapper if `D1` serves
    something else. It does, and the reason is worth a sentence rather than a
    parameter: the run history is ALREADY a paged list with a runbook filter
    (`07-endpoints.md` row 8), already ordered on a total key, already tested
    against 51 rows. A second paging surface on the detail would be the same
    list described twice, and two descriptions of one list is `G114`'s whole
    subject — three shipped Work screens drew empty tables over exactly that.
    So this payload carries the runbook's FACTS and its `last_run` summary; the
    Runs tab asks the history route for its page.

    ⚠ **AND IT DOES NOT SERVE `RunbookSetupView` EITHER, DELIBERATELY.** That
    type is a RENDERED view model — translated chrome labels, `SetupValue`
    wrappers, one-sentence copy. Serving it from Django would put screen copy in
    Python and out of the eleven locale catalogues, which is B14's line and not a
    style preference. `contract.py` rules the twelve BLOCK shapes to the
    renderer because a block payload is data with no words in it; a setup view
    is words. The mapper belongs where `runbooksEndpoints.ts` already put it.

    ⚠ **`PUT` CHANGES SCHEDULE, CAP, GATE, ENABLED AND VISIBILITY, AND WRITES A
    NEW VERSION** — `07-endpoints.md` row 3 plus `RB-050`'s *an Admin may widen
    or narrow it per runbook*. `services.update_runbook` holds the whole rule:
    an unknown field is refused, a frozen one is refused BY NAME, a no-op edit
    writes no version, and an edit to an Action drops the trust ratchet
    (`BR-RBS-036`) which `open_run` — not this route — enforces at the next run.

    ⚠ **AND `accept_template_update` IS A FIELD ON THIS BODY RATHER THAN A ROUTE
    OF ITS OWN, DELIBERATELY.** `07-endpoints.md` gives eighteen routes and none
    of them is *accept the offered template change*; adding a nineteenth address
    for what is, mechanically, an edit that writes a new version would be this
    lane widening a contract it is implementing. `{"accept_template_update":
    true}` on the edit route is the same act through the door that already
    exists, and it is idempotent — accepting an offer that is not there returns
    the runbook unchanged rather than refusing, because a double click is not an
    error a clerk should be shown.

    ⚠ **THE `PUT` ANSWERS THE WHOLE DETAIL PAYLOAD, NOT A BARE OK.** `RBS-004`
    redraws seven tabs from one object; a 200 with no body would make the screen
    fetch again to find out what it had just done, and the two reads could
    legitimately disagree if a sibling edited in between.
    """
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        runbook = selectors.runbook_by_key(tenant_id, key)
        if runbook is None:
            raise errors.NotFoundError()
        payload = dict(_payload(request))
        accept = bool(payload.pop("accept_template_update", False))
        services.update_runbook(runbook, payload, actor_id=_actor_id(request))
        if accept:
            services.accept_template_update(runbook, actor_id=_actor_id(request))
        return Response(selectors.runbook_detail(tenant_id, key))
    found = selectors.runbook_detail(tenant_id, key)
    if found is None:
        raise errors.NotFoundError()
    return Response(found)


# ── cutover plans (CR-075 wave J · US-RBS-008) ───────────────────────────────


@api_view(["GET", "POST"])
@permission_classes([ReadAnyRoleWriteSystemAdmin])
def cutover_plans(request: Any) -> Response:
    """`GET · POST /cutover-plans` — the go-live plans and their items.

    **GET** pages server-side (`NFR-3`, and this module has no unpaginated list
    anywhere). **POST** creates a plan with its items in one transaction; a
    NULL `runbook_key` on an item is a human task the engine never performs
    (`03-field-map.md` D-7), which is why the field is optional here rather than
    validated into existence.

    Staff read, Admin writes — `07-endpoints.md` §1's standing sentence, applied
    by `ReadAnyRoleWriteSystemAdmin` rather than by an `if` inside the view.
    `DEF-196` is what an `if` costs.
    """
    require_tenant(request)
    if request.method == "POST":
        payload = _payload(request)
        return Response(
            cutover.create_plan(
                name=payload.get("name"),
                go_live_on=payload.get("go_live_on"),
                items=payload.get("items"),
                actor_id=_actor_id(request),
            ),
            status=201,
        )
    params = parse_list_params(request.query_params)
    return Response(
        _envelope(request, cutover.plans_page(page=params.page, per=params.per))
    )


@api_view(["PATCH"])
@permission_classes([ReadAnyRoleWriteSystemAdmin])
def cutover_plan_item(request: Any, plan_id: str, seq: str) -> Response:
    """`PATCH /cutover-plans/{id}/items/{seq}` — tick, un-tick or re-own ONE item.

    ⚠ **THE ITEM IS ADDRESSED BY `seq` AND NOT BY ITS ID** (B14 rule 31). `seq`
    is UNIQUE per plan and is the number an implementer says out loud — *"item 4
    is still open"* — so the address a person can read is the address the route
    takes.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        cutover.update_item(
            plan_id=plan_id,
            seq=int(seq),
            status=payload.get("status"),
            owner=payload.get("owner"),
            actor_id=_actor_id(request),
        )
    )


@api_view(["POST"])
@permission_classes([ReadAnyRoleWriteSystemAdmin])
def cutover_plan_item_evidence(request: Any, plan_id: str, seq: str) -> Response:
    """`POST /cutover-plans/{id}/items/{seq}/evidence` — **Attach to plan ✓**.

    The run's result becomes the item's evidence, and a run whose verdict
    carries no blocker turns the item green on its own (`US-RBS-008` §7). Four
    refusals guard it and `cutover.attach_evidence` states each one — the run
    must be finished, it must be the runbook the item names, a human task
    refuses evidence entirely, and the figures come from the FROZEN report
    rather than being recomputed here.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        cutover.attach_evidence(
            plan_id=plan_id,
            seq=int(seq),
            run_id=payload.get("run_id"),
            actor_id=_actor_id(request),
        )
    )


# ⚠ **LITERALS FIRST, `<str:key>` LAST.** See `runbook_detail`'s docstring: the
# key pattern matches `runbooks/templates` and `runbooks/runs`, and Django takes
# the first pattern that matches. `runs/<str:run_id>/…` is three or four
# segments and out of collision range by construction, but the two-segment
# `runbooks/templates` and `runbooks/runs` are NOT — which is
# `integrations/subprocessors` exactly, and that one shipped.
#
# ⚠ **THE RESULT FILE IS A `re_path` SO THAT A THIRD WORD IS A 404.** A
# `<str:outcome>` converter is `[^/]+` and would match `results/anything.csv`,
# hand the view a word it has no file for, and — because `done = outcome ==
# "done"` — serve the *not done* file under any name a caller invented. The
# alternation makes `done` and `not-done` the only two addresses that exist,
# which is what `result_files.FILE_NAMES` says and what this module's docstring
# claims. A route whose docstring is stricter than its pattern is hard-won law 1
# in a URLconf.
# ══════════════════════════════════════════════════════════════════════════
# CR-075 WAVE H — THE WORK LIST (`US-RBS-006`, `07-endpoints.md` row 17)
#
# `GET · PATCH /work-items[/{id}]` — findings, exceptions and human tasks in one
# place; assign, resolve, reopen. **Staff read and staff write**, which is the
# one place this module departs from *"Staff reads; Admin writes"* and it is
# `07-endpoints.md` row 17's own `Staff` cell: resolving the item on your own
# desk is the job, and a work list only an Admin can tick is a work list nobody
# uses.
# ══════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([READ_ROLES])
def work_items_list(request: Any) -> Response:
    """`GET /work-items` — row 17: the work list, **paged on the server**.

    Filters are `BR-SHL-011`'s `f.<name>` grammar: `f.source`, `f.status`,
    `f.owner`. An unknown filter name is IGNORED and an unknown value falls back
    to unfiltered — a list URL never 4xx's over its own params.

    ⚠ **`f.status` DEFAULTS TO `open` AND THAT IS A CHOICE, NOT AN OMISSION.**
    The screen is *everything waiting on a person*; a default that included
    resolved rows would put last month's closed items on top of this morning's
    work. `f.status=resolved` and `f.status=all` are both reachable.
    """
    tenant_id = require_tenant(request)
    params = parse_list_params(
        request.query_params, allowed_sorts=(), default_sort=None, allowed_filters=()
    )
    status = _filter(request, "status")
    result = selectors.work_items_page(
        tenant_id,
        source_kind=_filter(request, "source"),
        status=None if status == "all" else (status or "open"),
        owner_id=_filter(request, "owner"),
        q=params.q,
        page=params.page,
        per=params.per,
    )
    # ⚠ **SPREAD, NEVER `_envelope(...).update(...)`.** That helper returns a
    # FRESH dict of exactly four keys and discards everything else, and
    # `asset_work_orders` forgot it — `maintenance_index` never left the server
    # (`DEF-AST-4120`). The chips are computed over the whole list and never
    # over the page: a chip that counted the page would read *All 50* on 900
    # rows, which is `NFR-3` broken one layer up.
    return Response(
        {
            **_envelope(request, result),
            "chips": selectors.work_item_counts(tenant_id),
        }
    )


@api_view(["PATCH"])
@permission_classes([READ_ROLES])
def work_item_detail(request: Any, item_id: str) -> Response:
    """`PATCH /work-items/{id}` — row 17: **assign, resolve, reopen**.

    Three verbs on one route because they are three values of one field plus an
    owner, and `US-RBS-006` §5 states each: *resolving stamps `resolved_at`;
    reopening clears it and keeps the row.*

    ⚠ **WHAT A PERSON MAY NOT DO IS HAVE A RESOLVED ITEM SILENTLY RE-RAISED AS
    A NEW ROW**, and that is the engine's guarantee rather than this route's:
    the fingerprint finds the row again and reopens it with its history
    (`TC-RBS-006.2`).

    An item of another tenant and one that never existed are the same 404.
    """
    tenant_id = require_tenant(request)
    item = selectors.work_item(tenant_id, item_id)
    if item is None:
        raise errors.NotFoundError()
    updated = services.update_work_item(
        item, _payload(request), actor_id=_actor_id(request)
    )
    return Response(selectors.work_item_row(updated))


urlpatterns = [
    path("runbooks/templates", runbook_templates),
    path("runbooks/runs", runs_list),
    path("runbooks/runs/<str:run_id>", run_detail),
    path("runbooks/runs/<str:run_id>/report", run_report),
    path("runbooks/runs/<str:run_id>/records", run_records),
    re_path(
        r"^runbooks/runs/(?P<run_id>[^/]+)/results/(?P<outcome>done|not-done)\.csv$",
        run_result_file,
    ),
    path("cutover-plans", cutover_plans),
    path("cutover-plans/<str:plan_id>/items/<str:seq>", cutover_plan_item),
    path("cutover-plans/<str:plan_id>/items/<str:seq>/evidence", cutover_plan_item_evidence),
    path("runbooks", runbooks_list),
    path("runbooks/<str:key>/clone", runbook_clone),
    # CR-173-BRC10 — a run by hand. Three segments, literal tail, before the key.
    path("runbooks/<str:key>/runs", runbook_runs),
    # Four segments, out of collision range with the two-segment key pattern —
    # and registered before it anyway, because *literals first* in this file has
    # no exceptions and an exception is what a later lane copies.
    path("runbooks/<str:key>/domains/<str:parameter>", runbook_parameter_domain),
    path("runbooks/<str:key>", runbook_detail),
    # ⚠ **`work-items` IS NOT UNDER `runbooks/`, AND THAT IS `07-endpoints.md`
    # ROW 17's OWN ADDRESS.** The list holds three kinds of row and only two of
    # them come from a runbook: a human task from a cutover plan has no run at
    # all. Nesting it would say the opposite in the URL.
    path("work-items", work_items_list),
    path("work-items/<str:item_id>", work_item_detail),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-003 · US-RBS-018 (EP-RBS-01; CR-075 wave D task D1; 07-endpoints.md rows 1·2·4·8·9·10·11·14 quoted verbatim) · US-RBS-038 · US-RBS-040 (CR-075 wave E task E1; rows 3·5·6 — the three WRITE routes) · US-RBS-018 again (wave D task D5 — role visibility narrows the catalogue and the library)
# generated: 2026-09-06 by the CR-075 wave D build lane; extended 2026-09-06 by the wave E lane
# checklist: A✔ B✔ C✔ D✔(eleven method-and-path pairs across nine addresses, all resolved through config/urls.py by the tests) E=deferred(no-frontend-half — the Add, Clone and Change controls are three sibling lanes' and their holds have now EXPIRED: `DEF-RBS-4311`) F✔ G✔ H=n/a(thin routes; no 🔒 path — nothing here composes an idempotency key, touches rating math or posts a ledger line; the wave E MIGRATION is 🔒 and carries its own marker and ledger row)
# gates: pytest tests/test_us_rbs_003_endpoints.py · tests/test_us_rbs_038_definition_surface.py · tests/test_us_rbs_003_pg.py · tests/test_us_rbs_038_pg.py (PostgreSQL) · G27 · G6 (no ORM in api.py) · G9 · G32 (all five wave E refusal keys resolve) · G114 (one envelope) · G115 (the import census)
# exceptions: `CsvRenderer` is copied from apps/metering/api.py rather than shared — a cross-module import for four lines is a coupling G115 is right to refuse, and the reason is in its docstring · `ReadAnyRoleWriteSystemAdmin` is declared HERE rather than in core/permissions.py, because `07-endpoints.md` §1's *Staff reads* is all three roles and `SettingsReadAnyWriteSystemAdmin`'s set is `A4`'s narrower settings row — widening that one re-opens `DEF-196`, which is why `ShellDisplayRead` was also a new class in the module that needed it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
