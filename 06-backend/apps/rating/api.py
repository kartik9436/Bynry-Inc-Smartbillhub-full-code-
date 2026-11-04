# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001 (GET /plans + DELETE /plans/{id}) · US-RAT-002 (POST /plans ·
#           PATCH /plans/{id}) · US-RAT-003 (POST /plans/{id}/publish · /archive) ·
#           US-RAT-004 (GET /rate-schedules · POST /rate-schedules/{id}/archive) ·
#           US-RAT-005/006/007 (POST /rate-schedules · PATCH · /activate) ·
#           US-RAT-008 (GET/POST /charges · PATCH · /deactivate · DELETE) ·
#           US-RAT-009 (GET/POST /taxes · PATCH · /deactivate · GET
#           /tax-jurisdictions) · BR-RAT-069 (available ≠ granted — `plans` and
#           `enrolled` are two different counts) · BR-RAT-079 (restricted proof —
#           the discount reads serve counts, never documents or account ids) ·
#           BR-RAT-087 (money and percent carry a `*_display` companion) ·
#           US-RAT-010 (POST /rate-schedules/{id}/versions ·
#           GET /rate-changes) · US-RAT-011 (POST /rate-changes → 202 + job_id)
#           Screens: S9 · S10 · S11 · S12 · S13
# Change:   CR-013 part 3 — GET /discounts + GET /discounts/{id}, the read half
#           of §18 rows 10 (DIS-01 landing tab) and 11 (CHG-01.discount).
#           AMENDED 2026-08-21 by the DIS-02 lane: POST /discounts and POST
#           /discounts/{id}/versions, the write half §18 row 12 needs. No
#           rule and no arithmetic is added here — both delegate to
#           `discount_services`, which this lane does not edit (🔒).
#           AMENDED 2026-08-21 by the Wave C lane (DEF-400): the three LIFECYCLE
#           routes — submit, approve, activate — so a draft discount can reach
#           `Active` from a screen. Same posture: pure delegation, 🔒 untouched.
#           AMENDED 2026-09-18 by the `DEF-RAT-5742` lane (`NFR-3`): `_prepaged`
#           replaces `_paginated` on ALL SIX list views. `_paginated` handed DRF
#           a LIST, which has to exist in full before it can be sliced, so every
#           list built the whole catalogue to draw fifty rows. The selectors now
#           take the page in SQL and this file builds the SAME envelope over it
#           — `count`/`next`/`previous`/`results` in that order, `extra` after
#           them — and re-clamps `page`, because `StandardPagination.
#           get_page_number` is no longer in this path (`BR-SHL-011`). No row
#           builder was touched, so no figure moves (hard rule 2) and the charge
#           code still owns the base amount (`BR-RAT-088`).
# Rules:    BR-RAT-030 (lifecycle endpoints) · BR-RAT-031 (no approve endpoint —
#           the workflow is REMOVED) · BR-RAT-037 (versions append-only; the log
#           has no mutation route) · BR-RAT-040 (bulk = one atomic batch, 202) ·
#           BR-SHL-011 (list grammar q/sort/dir/page/per/f.<name> via BE-05) ·
#           A4 (Plans & Rates: View for staff, writes System-Admin-only —
#           server-enforced per BR-IDN-009/G13)
# Tests:    06-backend/tests/test_us_rat_plans.py · test_us_rat_schedules.py ·
#           test_us_rat_charges_taxes.py · test_us_rat_versioning.py ·
#           test_def_rat_5742_rating_lists_page_in_sql.py (NFR-3 — the page is
#           taken in SQL; asserts the STATEMENTS, never a returned row count)
# Impacts:  A11 Addendum r2 + 11b §2.4 inventory (typed client FI-01) ·
#           config/urls.py inclusion (wiring lane — urlpatterns exported here)
# ───────────────────────────────────────────────────────
"""rating API endpoints per A11 as amended by 11b §2.4 (PO-ratified via A11
Addendum r2).

THIN by law (B8/LAW 0): every write goes through services (sole writer), every
read through selectors; no ORM here. Refusals are catalog exceptions rendered
by the BE-02 handler; role gates are the BE-04 permission classes AND the
service-layer @require_role guards (defense in depth, BR-SHL-025).

Endpoints beyond the 11b §2.4 rows, added because a capability-matrix row
action or a ratified TC needs a server half — each REPORTED in the build
report, none invented for convenience:
  DELETE /plans/{id}                  US-RAT-001 TC-5 hard-delete audit-lock
  POST   /rate-schedules/{id}/duplicate DEF-370 — CR-013 part 1's "Duplicate
         (the normal way to start a filing)". Creates a NEW schedule carrying a
         DRAFT copy; the source is read and never written, so BR-RAT-037 cannot
         be reached through it.
  POST   /rate-schedules/{id}/archive US-RAT-004 TC-4 archive audit-lock
  DELETE /charges/{id}                US-RAT-008 TC-7 delete audit-lock
  GET    /tax-jurisdictions           S13 step-1 picker (BR-TEN-037) — PAGED
         since 2026-09-19 (DEF-RAT-5754/NFR-3); it served a bare array until
         then, and the client follows `count` so the picker still sees them all
  GET    /rate-changes                the S9 History view (EP-RAT-04 matrix)
  GET    /discounts                   DIS-01, §18 row 10 (CR-013 part 3)
  POST   /discounts                   DIS-02 create, §18 row 12 (CR-013 part 3)
  GET    /discounts/{id}              CHG-01.discount, §18 row 11 (BR-RAT-084)
  PATCH  /discounts/{id}              BR-RAT-1016 verb 1 — the IDENTITY only
  POST   /discounts/{id}/versions     DIS-02 edit — a NEW dated version, never a PATCH
  PATCH  /discounts/{id}/versions/{vid}             BR-RAT-1016 verb 1 — a never-submitted DRAFT
  POST   /discounts/{id}/versions/{vid}/corrections BR-RAT-1016 verb 2 — the SAME window
  POST   /discounts/{id}/versions/{vid}/submit    DEF-400 — BR-RAT-077 computes here
  POST   /discounts/{id}/versions/{vid}/approve   DEF-400 — BR-RAT-083's second act
  POST   /discounts/{id}/versions/{vid}/activate  DEF-400 — the version in force
There is deliberately NO approve endpoint for a RATE SCHEDULE and no
rate_change_log mutation route (BR-RAT-031 as-modified · BR-RAT-037 append-only).
⚠ The three discount routes above are NOT an exception to BR-RAT-031: that rule
removed the rate-schedule approval workflow, and CR-013 part 3 asks for a
discount one by name (*"approval authority with a second approval above a
subsidy threshold"*), ruled into BR-RAT-077 and BR-RAT-083.

`urlpatterns` is exported for inclusion by config/urls.py — the include itself
is the platform wiring lane's one-liner (config/ is outside this packet's
territory; recorded in the build report).
"""

import math
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response

from apps.rating import discount_reads, discount_services, plan_reads, plan_writes, seams, selectors, services
from core import errors
from core.pagination import ListParams, StandardPagination, parse_list_params
from core.permissions import SYSTEM_ADMIN, AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant, tenant_path


def _actor(request: Any) -> Any:
    """The acting user for the B12 §6a service shape: id from the session user,
    role server-attached by the identity layer (BE-04) — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="rating.payload_not_object")
    return data


def _prepaged(
    request: Any,
    params: ListParams,
    fetch: Callable[[ListParams], tuple[list[dict[str, Any]], int]],
    extra: dict[str, Any] | None = None,
) -> Response:
    """The DRF envelope over a page the SELECTOR already took (`NFR-3`).

    ⚠ **WHAT THIS REPLACED, AND WHY IT HAD TO (`DEF-RAT-5742`).** Until
    2026-09-18 every list in this module went through `_paginated`, which
    called `paginator.paginate_queryset(rows, request)` on a **list** — and a
    list has to exist in full before it can be sliced. So all six lists built
    every matching row and threw all but fifty away: `GET /plans` on a thousand
    plans was about two thousand statements to draw one screen, because
    `plan_row` reads `PlanService` and `PlanRateSchedule` per row. `extra` did
    not make that necessary and neither did the envelope; a list was simply the
    shape the helper took. The `*_page` selectors return `(rows, total)` with
    the page in a SQL `LIMIT`/`OFFSET` and the count in a `COUNT(*)`, so there
    is nothing left here to slice.

    ⚠ **THE ENVELOPE IS BYTE-FOR-BYTE THE ONE EVERY OTHER LIST SERVES** —
    `count` / `next` / `previous` / `results`, in that order, with the page
    links built by DRF own `replace_query_param` / `remove_query_param` so
    `?page=2` is formed here exactly as it is on the thirty endpoints that
    still hand the paginator a queryset. A second envelope shape on five
    catalogue screens would be a client-side special case for ever, which is
    the sentence `customers._prepaged` already makes about the accounts list.
    `extra` is appended AFTER the four keys, exactly where `_paginated` put it,
    so the S9 header roll-up travels unchanged.

    ⚠ **`page` IS RE-CLAMPED HERE AND NOT ONLY IN THE PARSER (`BR-SHL-011`).**
    `parse_list_params` clamps `page` to >= 1 but cannot know the LAST page — it
    has counted nothing yet — and `StandardPagination.get_page_number`, which
    does that clamp for the queryset path, is no longer in this path at all. So
    it is done here, and the page is FETCHED AGAIN when the clamp moved it:
    serving the rows we were already handed would answer `?page=999` on a
    three-page list with a blank table and a `previous` link to page 998. Clamp,
    never error.

    ⚠ **THIS IS A SECOND COPY OF `customers._prepaged` AND THAT IS DELIBERATE
    BUT NOT DESIRABLE.** Its home is `core/pagination.py`, beside
    `StandardPagination` and `order_terms` — the same reasoning `order_terms`
    own docstring gives for existing at all. This lane owns `apps/rating/` and
    not `core/`, so the move is recorded in the decision log of 2026-09-18
    rather than taken here; a third copy should trigger it instead of being
    written.
    """
    from rest_framework.utils.urls import remove_query_param, replace_query_param

    rows, total = fetch(params)
    per = max(params.per, 1)
    pages = max(1, math.ceil(total / per)) if total else 1
    number = min(max(params.page, 1), pages)
    if number != params.page:
        rows, total = fetch(replace(params, page=number))
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


def _created(request: Any, body: dict[str, Any], location: str) -> Response:
    """201 + a Location a client can actually follow: absolute inside THIS
    request's tenant prefix (`/api/{tenant}/plans/…` — PO ruling 2026-08-10)."""
    response = Response(body, status=201)
    response["Location"] = tenant_path(request, location)
    return response


# ── S9 Plans tab + S10 wizard (11b §2.4) ────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # US-RAT-001 TC-6: staff read; POST is admin-gated below
def plans(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        payload = _payload(request)
        # `CR-167-BRC10` §7.3 — the contract body (`details` …, `publish`) goes
        # through `plan_writes`; the 8-step form's body still goes straight to
        # `services` until task 8 retires that form.
        if plan_writes.is_contract_body(payload):
            plan = plan_writes.create(_actor(request), payload)
        else:
            plan = services.create_plan(_actor(request), payload)
        return _created(request, plan, f"/plans/{plan['id']}")
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.PLAN_SORTS,
        default_sort=selectors.PLAN_DEFAULT_SORT,
        allowed_filters=selectors.PLAN_FILTERS,
    )
    return _prepaged(
        request, params, plan_reads.plan_page, {"rollup": selectors.rating_rollup()}
    )


def _as_of(request: Any, key: str = "as_of") -> date | None:
    """`?as_of=YYYY-MM-DD` — refused by name when it is not a date."""
    raw = request.query_params.get(key)
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="rating.not_a_date",
            field_errors=[{"field": key, "code": errors.VAL_FORMAT, "message_key": "rating.not_a_date"}],
        ) from None


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def plan_form_options(request: Any) -> Response:
    """`CR-167-BRC10` §7.3 — what the New/Edit form offers on `?on=` (the date
    the version starts), each item a `ref` with its version and from-date."""
    require_tenant(request)
    classes = [one for one in (request.query_params.get("classes") or "").split(",") if one]
    return Response(plan_reads.form_options(_as_of(request, "on"), classes))


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def plan_item(request: Any, plan_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        payload = _payload(request)
        if plan_writes.is_contract_body(payload):
            return Response(plan_writes.patch(_actor(request), plan_id, payload))
        return Response(services.update_plan(_actor(request), plan_id, payload))
    if request.method == "DELETE":
        services.delete_plan(_actor(request), plan_id)
        return Response(status=204)
    # `CR-167-BRC10` §7.3 — today's body PLUS the sections read AS OF a date
    # (`?as_of=`, default the utility's today; `versions` is the superset with
    # windows and states).
    body = selectors.plan_detail(plan_id)
    # `DEF-CUS-9821` — `?classes=` (an account's class, New Connect step 2)
    # narrows each service's base the way the bill picks it; absent, unchanged.
    classes = [one for one in (request.query_params.get("classes") or "").split(",") if one]
    body.update(plan_reads.plan_sections(plan_id, _as_of(request), classes or None))
    return Response(body)


class _CsvFormat(BaseRenderer):
    """`DEF-RAT-9359` — lets `?format=csv` THROUGH DRF's content negotiation.

    DRF reads `?format=` as its own override (`URL_FORMAT_OVERRIDE`) and, with
    no renderer whose `format` is `csv`, answers 404 before the view runs — so
    the Units and Audit downloads never reached `_csv_response`. The views
    return a `StreamingHttpResponse` and never call `render`; this class only
    exists for the negotiation step (metering's `CsvRenderer`, `DEF-553`, is
    the same cure; rating may not import metering, B1). JSON stays FIRST, so a
    request without `format=csv` is answered exactly as before."""

    media_type = "text/csv"
    format = "csv"

    def render(self, data: Any, accepted_media_type: Any = None, renderer_context: Any = None) -> Any:
        return data


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([JSONRenderer, _CsvFormat])
def plan_units(request: Any, plan_id: str) -> Response:
    """CR-087 D5 / PRB-21 — the units this plan prices, PAGED FROM THE SERVER.

    The plan's page showed a count of 74 with no way to see what was in it, and
    nothing said whether 74 meant units, accounts or customers. Rating has
    counted unit→plan assignments since `plan_row` — that is where 74 comes
    from — and no endpoint returned them.

    ⚠ **THE PAGINATION IS THE POINT, NOT THE PLUMBING (`NFR-3`).** The paginator
    is handed the QUERYSET, so the `count` in the envelope is a SQL `COUNT` over
    the WHOLE set and the page is a SQL `LIMIT`/`OFFSET`. Only the page's rows
    are then enriched through the seam. Handing it a built list — which is what
    every other list read in this module does, and what `GET /outstandings` is
    breaching at T5 — would materialise every unit of a 40,000-account tenant to
    render fifty of them, and the tile's total and the table would still have to
    agree by luck.

    ⚠ **NO FILTERS, NO SORT, DELIBERATELY.** The blueprint draws one table,
    sorted by premises, with no controls; `BR-SHL-011`'s grammar admits `page`
    and `per`, which the paginator reads, and an undeclared param is ignored
    rather than erroring. A filter nobody asked for is a control with no ruling
    behind it.
    """
    require_tenant(request)
    selectors.plan_or_404(plan_id)  # a plan that is not this tenant's is a 404
    # ⚠ AMENDED 2026-10-03 (`CR-167-BRC10` §7.3, ruling 13, images 31–33): the
    # drawing now draws a search, an occupancy filter and a CSV, so the "NO
    # FILTERS" paragraph above is history. All three stay SQL: `q` matches
    # unit or premises, `f.occupancy` is a customers sub-select (J11), and
    # `format=csv` streams the WHOLE filtered set.
    q = request.query_params.get("q", "")
    occupancy = request.query_params.get("f.occupancy")
    if request.query_params.get("format") == "csv":
        return _csv_response(plan_reads.plan_units_csv(plan_id, q, occupancy), "plan-units.csv")
    paginator = StandardPagination()
    page = paginator.paginate_queryset(plan_reads.plan_units_filtered(plan_id, q, occupancy), request)
    return paginator.get_paginated_response(selectors.plan_unit_rows(list(page or [])))


def _csv_response(chunks: Any, filename: str) -> Any:
    from django.http import StreamingHttpResponse

    from core.tenancy import current_tenant_id, stream_within_tenant_context

    # `G58` — WSGI iterates the body AFTER the tenant middleware has unset the
    # context, so the body carries its own (hard rule 1).
    response = StreamingHttpResponse(
        stream_within_tenant_context(current_tenant_id(), chunks),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([JSONRenderer, _CsvFormat])
def plan_audit(request: Any, plan_id: str) -> Response:
    """`CR-167-BRC10` §7.3 — the plan's Audit in WORDS, paged in SQL: the plan's
    own changes and what moved underneath it (schedules, charge codes, taxes,
    discounts). `f.kind=plan|underneath`, `f.from`, `f.to`, `format=csv`."""
    require_tenant(request)
    selectors.plan_or_404(plan_id)
    kind = request.query_params.get("f.kind")
    date_from = _as_of(request, "f.from")
    date_to = _as_of(request, "f.to")
    if request.query_params.get("format") == "csv":
        return _csv_response(
            plan_reads.plan_audit_csv(plan_id, kind, date_from, date_to), "plan-audit.csv"
        )
    paginator = StandardPagination()
    page = paginator.paginate_queryset(
        plan_reads.plan_audit_queryset(plan_id, kind, date_from, date_to), request
    )
    return paginator.get_paginated_response(plan_reads.plan_audit_rows(list(page or [])))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_versions_create(request: Any, plan_id: str) -> Response:
    """`BR-RAT-1066` — *Change from a date*: a new dated version, saved
    (`publish:false`) or published."""
    require_tenant(request)
    return _created(
        request,
        plan_writes.new_version(_actor(request), plan_id, _payload(request)),
        f"/plans/{plan_id}",
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_duplicate(request: Any, plan_id: str) -> Response:
    """`DEF-RAT-9352` — *Duplicate* (image 25): a NEW draft plan offering what
    this one offers today, under the `name` and `code` given. 201 with a
    Location on the NEW plan; the source is read and never written."""
    require_tenant(request)
    result = plan_writes.duplicate(_actor(request), plan_id, _payload(request))
    return _created(request, result, f"/plans/{result['id']}")


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_version_publish(request: Any, plan_id: str, version_no: int) -> Response:
    """`BR-RAT-1066` — publish a saved new version (*Publish new version*)."""
    require_tenant(request)
    return Response(plan_writes.publish_version(_actor(request), plan_id, version_no))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_publish(request: Any, plan_id: str) -> Response:
    require_tenant(request)
    return Response(services.publish_plan(_actor(request), plan_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_archive(request: Any, plan_id: str) -> Response:
    require_tenant(request)
    return Response(services.archive_plan(_actor(request), plan_id))


@api_view(["GET"])
def plan_bound_changes(request: Any, plan_id: str) -> Response:
    """PO ruling 2026-09-18 — **A PLAN IS TOLD WHEN WHAT IT BINDS CHANGES.**

    Verbatim: *"yes we should build this. It measn every time Rate, taxes,
    Charge code, Discounts are changed, at apporval we need to take action to
    inform Plan about it - Fix this"*.

    It follows from the PO's own correction of the same day — *"plan will not do
    any edits to Rates … plan only binds it"*, which is `BR-RAT-088` restated.
    Once money lives entirely on the bound objects, **the plan's whole job is to
    show what it is bound to, and it was showing only half of that**: which
    schedule it binds, and never that the bound schedule's price moved.

    ⚠ **READ-ONLY, AND NOT ADMIN-ONLY.** Every write in this module is
    `SystemAdminOnly`; this reads a log a clerk needs in order to understand a
    bill they are being asked about, and gating it would put the answer behind
    the one person who is not on the phone. Tenant scoping is the guard that
    matters here (hard rule 1) and `require_tenant` is it.

    ⚠ **PAGINATED FROM THE SERVER, AND THE PAGINATION IS THE POINT (`NFR-3`).**
    The paginator is handed the QUERYSET, so `count` is a SQL `COUNT` over the
    whole set and the page is a SQL `LIMIT`/`OFFSET`. One tax or one charge code
    reaches EVERY plan that binds it, so this set grows with the ESTATE rather
    than with the plan — and `NFR-5` forbids a cap anywhere.

    ⚠ **IT IS NOT A PLAN VERSION AND MUST NEVER BECOME ONE.** A bound object
    changing is not a change to the PLAN — that is the whole point of the PO's
    ruling — so nothing here writes `plan_versions` and `rate_plans.version`
    does not move. A lane that "fixes" this by minting a version has inverted it.

    ⚠ **THE ANSWER CARRIES WHAT IT COULD NOT SEE (`DEF-RAT-5738`).** Only
    `schedule` and `charge` rows are ever written to `rate_change_log`; no tax
    and no discount path writes one. `coverage` names both lists so the screen
    can say so, rather than drawing an empty tax section that reads as good news
    — hard-won law 7, *reporting zero over a scope it silently excludes*.
    """
    require_tenant(request)
    selectors.plan_or_404(plan_id)  # a plan that is not this tenant's is a 404
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.plan_bound_changes_queryset(plan_id), request)
    response = paginator.get_paginated_response(
        selectors.plan_bound_change_rows(list(page or []))
    )
    # ⚠ BESIDE the envelope, never inside `results`: the envelope is
    # `{count, next, previous, results}` everywhere in this product (`G114`),
    # and a per-page key would repeat a fact about the WHOLE view on every page.
    response.data["coverage"] = selectors.plan_bound_change_coverage()
    return response


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_corrections(request: Any, plan_id: str) -> Response:
    """`OQ-RAT-12409` option A — `BR-RAT-1016` verb 2 for the PLAN.

    The route spelling is the other four objects' spelling on purpose
    (`POST …/corrections`, a collection a correction is MINTED into), because
    `BR-RAT-1016` rules that the three verbs are the same for every priced
    object and a fifth spelling is a cost paid by every future reader.

    ⚠ **200, NOT 201, AND THAT IS THE ONE DIVERGENCE FROM `tax_corrections`.**
    A tax correction creates a NEW TAX and the Location header points at it, so
    a client can read what is now in force. A plan correction restates the SAME
    plan at the SAME version number — `rate_plans.version` does not move and no
    new plan exists — so the thing a client must read back is the plan it
    already has. A 201 with a Location pointing at the unchanged plan id would
    say a resource was created that was not.
    """
    require_tenant(request)
    payload = _payload(request)
    if plan_writes.is_contract_body(payload):
        return Response(plan_writes.correct(_actor(request), plan_id, payload))
    return Response(services.correct_plan_version(_actor(request), plan_id, payload))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def plan_taxes(request: Any, plan_id: str) -> Response:
    """BR-RAT-113 — attach ONE catalogue tax/fee to this plan (PLN-03 step 5).

    Body: `{"tax": <tax id>, "reason": <required when the plan is PUBLISHED —
    BR-RAT-037>}`. ADD-ONLY by ruling: there is no payload that omits a
    jurisdiction-mandated tax, and the DELETE below refuses to."""
    require_tenant(request)
    return Response(services.attach_tax_to_plan(_actor(request), plan_id, _payload(request)))


@api_view(["DELETE"])
@permission_classes([SystemAdminOnly])
def plan_tax_item(request: Any, plan_id: str, tax_id: str) -> Response:
    """Detach an EXPLICIT attachment only. A jurisdiction-mandated tax has no
    attachment row to delete and the attempt is refused BY NAME citing
    BR-RAT-094 (`rating.plans.mandated_tax_not_detachable`) — whether staff may
    detach a mandated tax is exactly the question BR-RAT-113 left unruled."""
    require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    return Response(services.detach_tax_from_plan(_actor(request), plan_id, tax_id, body))


# ── S9 Rate schedules tab + S11 wizard ──────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def rate_schedules(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        schedule = services.create_rate_schedule(_actor(request), _payload(request))
        return _created(request, schedule, f"/rate-schedules/{schedule['id']}")
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.SCHEDULE_SORTS,
        default_sort=selectors.SCHEDULE_DEFAULT_SORT,
        allowed_filters=selectors.SCHEDULE_FILTERS,
    )
    return _prepaged(request, params, selectors.schedule_page)


@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])
def rate_schedule_item(request: Any, tariff_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        return Response(
            services.update_rate_schedule(_actor(request), tariff_id, _payload(request))
        )
    return Response(selectors.schedule_detail(tariff_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def percent_basis_options(request: Any) -> Response:
    """**Based on** — which services this schedule may take a percentage OF.
    `CR-130-BRC07` §3 · PO ruling 2026-09-22.

    `?service=<code>&basis=usage|charge`. The list is DERIVED from what the
    tenant has switched on and from what the chosen basis can actually supply
    (`selectors.percent_basis_options`); **no service code appears in any
    condition**, which is the ruling — *"dont hard code anything - use logic to
    derive it so that it is flexible and handle any scenario."*

    ⚠ **IT EXISTS SO THE DERIVATION IS NOT WRITTEN TWICE.** The wizard already
    receives every enabled service with its `billing_basis` on the Settings
    payload and could filter client-side — and that is precisely the shape
    CLAUDE.md's hard-won law 2 names: the front end types the service list out
    by hand in two places, so an eleventh service *"does NOT appear on screen on
    its own and it fails SILENTLY"*. One answer, served, is one place to fix.

    A READ, gated as one (`AnyTenantRole`), and unpaginated by SHAPE rather
    than by size: it returns the tenant's enabled services, which `BR-RAT-024`
    caps at the platform catalogue's eleven. `NFR-3` is about lists that grow
    with the utility; this one cannot.
    """
    require_tenant(request)
    return Response(
        {
            "results": selectors.percent_basis_options(
                request.query_params.get("service") or None,
                request.query_params.get("basis") or None,
            )
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def rate_schedules_base_to_choose(request: Any) -> Response:
    """`DEF-RAT-9797` (PO ruling 2026-10-06: a rate schedule names exactly one
    base charge code) — the live schedules that name none while their service
    has one. Since 2026-10-06 (`DEF-RAT-9832`, PO ruling) they bill a `$0.00`
    base with a warning until a System Admin chooses — no code is taken from
    the pool; this is what the Rate schedules notice counts and names.

    Unpaginated on its own facts: bounded by the tenant's own live schedules
    (tens), and it is a to-do list whose length IS the message."""
    require_tenant(request)
    rows = selectors.schedules_needing_a_named_base()
    return Response(
        {
            "count": len(rows),
            "results": [
                {"id": str(row.id), "name": row.name, "service": row.service.code} for row in rows
            ],
        }
    )


# `DEF-RAT-10026` (PO 2026-10-09, *"yes please do it"*) — `charge_base_clash`
# (`GET /charges/base-clash`, `DEF-RAT-9799`) stood here and is RETIRED with the
# save-time refusal it mirrored: a service may hold two or more base codes for
# the same customer class, so step 1 has nothing to warn about. Its one caller
# (`useBaseCodeClash`, New/Edit charge code step 1) went in the same commit.


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def rate_schedule_rates(request: Any, tariff_id: str) -> Response:
    """`CR-157-BRC10` wave B — the Rates tab's *Base charges* table and the
    *Sizes priced* tile, for the schedule as it stands today
    (`schedule_reads.schedule_rates`). A READ, gated as one.

    Unpaginated by SHAPE: one row per connection size THIS schedule prices,
    which is bounded by the tenant's size catalogue for one service (water has
    five, trash seven) and does not grow with accounts — `NFR-3` is about lists
    that grow with the utility. The Units column is one grouped count, however
    many units are on the schedule."""
    require_tenant(request)
    from apps.rating import schedule_reads

    return Response(schedule_reads.schedule_rates(tariff_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def rate_schedule_plans(request: Any, tariff_id: str) -> Response:
    """`CR-157-BRC10` wave B — the Plans tab: Plan · Code · Customer class ·
    Status · Units, with *Class differs*. PAGED IN SQL (`NFR-3`): the paginator
    is handed a queryset, so `count` is a `COUNT(*)` and only the page is
    enriched. It replaces the tab's client-side scan of the first 200 plans.
    No filters, no sort — the drawing draws one table with no toolbar."""
    require_tenant(request)
    from apps.rating import schedule_reads

    tariff = selectors.tariff_or_404(tariff_id)  # another tenant's id is a 404
    paginator = StandardPagination()
    page = paginator.paginate_queryset(schedule_reads.schedule_plans_queryset(tariff), request)
    return paginator.get_paginated_response(
        schedule_reads.schedule_plan_rows(tariff, list(page or []))
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def rate_schedule_impact(request: Any, tariff_id: str) -> Response:
    """CR-013 part 1 step 4's MANDATORY impact analysis (DEF-434).

    Part 1, verbatim: *"effective/end dates plus mandatory impact analysis:
    accounts affected by plan, average and worst-case bill change per class,
    annualised revenue change, accounts over threshold"*, glossed as *"MANDATORY
    and is four figures, not a warning banner"*. Until this route existed
    `GET /rate-schedules/{id}` served `used_by_plans` and `applied_to_accounts`
    and nothing else, so three of the four figures were stated absences on the
    screen and BR-RAT-091 clause 2's `10%` gate read a number nobody computed.

    A READ, and gated as one (`AnyTenantRole`, like every other rating read):
    it prices, it does not write, and a clerk who may look at a rate schedule
    may look at what changing it would do. The ENFORCEMENT lives on the write —
    `services.create_rate_schedule_version` — so nothing depends on a client
    having asked this question first.

    `effective_from` (ISO date) and `version_id` are both optional. The default
    is the schedule's saved draft, or its latest version, compared against
    whatever it replaces.
    """
    require_tenant(request)
    raw_date = request.query_params.get("effective_from") or ""
    effective_from = None
    if raw_date:
        try:
            effective_from = date.fromisoformat(raw_date)
        except ValueError:
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="rating.schedules.effective_from_invalid"
            )
    return Response(
        selectors.rate_change_impact(
            tariff_id,
            effective_from=effective_from,
            proposed_version_id=request.query_params.get("version_id") or None,
        )
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def rate_schedule_activate(request: Any, tariff_id: str) -> Response:
    require_tenant(request)
    return Response(services.activate_rate_schedule(_actor(request), tariff_id, _payload(request)))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def rate_schedule_versions(request: Any, tariff_id: str) -> Response:
    require_tenant(request)
    result = services.create_rate_schedule_version(_actor(request), tariff_id, _payload(request))
    return _created(request, result, f"/rate-schedules/{tariff_id}")


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def rate_schedule_version_corrections(request: Any, tariff_id: str, version_id: str) -> Response:
    """`BR-RAT-1016` verb 2 — correct a LIVE version over the SAME window.

    ⚠ **IT IS A POST TO A COLLECTION AND NOT A PATCH, AND THE SHAPE IS THE
    RULE.** A correction MINTS a row; the corrected version is never rewritten.
    The same spelling `POST /taxes/{id}/corrections` and
    `POST /discounts/{id}/versions/{vid}/corrections` already use — the fifth
    and last of `BR-RAT-1016`'s priced objects, answering the question the way
    the other four answer it. Two objects answering one question two ways is
    the whole finding the PO was shown.

    Deliberately NOT a flag on `/versions`: one endpoint with a boolean would
    let a caller turn a rate change into a correction by flipping a field.
    """
    require_tenant(request)
    return Response(
        services.correct_rate_schedule_version(
            _actor(request), tariff_id, version_id, _payload(request)
        )
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def rate_schedule_duplicate(request: Any, tariff_id: str) -> Response:
    """DEF-370 · CR-013 part 1's *"Duplicate (the normal way to start a
    filing)"*. 201 with a Location on the NEW schedule, because that is what was
    created — the source is read and never written."""
    require_tenant(request)
    result = services.duplicate_rate_schedule(_actor(request), tariff_id, _payload(request))
    return _created(request, result, f"/rate-schedules/{result['id']}")


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def rate_schedule_discard_draft(request: Any, tariff_id: str) -> Response:
    """DEF-RAT-6447 — throw away the parked draft, keep the live rate.

    POST rather than DELETE because the schedule is not what is being deleted:
    the draft is one row inside it and the answer is the schedule as it now
    stands, which is what the wizard reloads from.
    """
    require_tenant(request)
    return Response(services.discard_rate_schedule_draft(_actor(request), tariff_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def rate_schedule_archive(request: Any, tariff_id: str) -> Response:
    require_tenant(request)
    return Response(services.archive_rate_schedule(_actor(request), tariff_id))


# ── S9 Charge codes tab + S12 form ──────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def charges(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        charge = services.create_charge(_actor(request), _payload(request))
        return _created(request, charge, f"/charges/{charge['id']}")
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.CHARGE_SORTS,
        default_sort=selectors.CHARGE_DEFAULT_SORT,
        allowed_filters=selectors.CHARGE_FILTERS,
    )
    # CR-156-BRC10 — the *All · Base · Plan · Other* chips' counts ride the
    # list's own envelope (one GROUP BY), so the chips and the table are
    # answered by the same filters in the same request.
    return _prepaged(
        request,
        params,
        selectors.charge_page,
        extra={"kind_counts": selectors.charge_kind_counts(params)},
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def charge_picker(request: Any) -> Response:
    """`CR-156-BRC10` · CHG-02 step 1's *Code* — the Settings codes NOT IN USE
    (PO 2026-10-01: *"when user select code from list show what are not in use
    only"*), of the asked kind or of no kind yet, for a base of the asked
    service or of none. `?kind=base|plan|other&service=<code>`.

    Unpaginated deliberately and on its own facts, not by reference to any
    other list: its rows are bounded by the codes a utility has MINTED on
    Settings and not yet configured (tens, never thousands), and a type-ahead
    over a page would hide a free code past the page edge."""
    require_tenant(request)
    kind = str(request.query_params.get("kind") or "").strip().lower()
    if kind not in ("base", "plan", "other"):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="rating.unknown_value",
            field_errors=[
                {
                    "field": "kind",
                    "code": errors.VAL_UNKNOWN_LOOKUP,
                    "message_key": "rating.unknown_value",
                    "params": {},
                }
            ],
        )
    service = str(request.query_params.get("service") or "").strip() or None
    body: dict[str, Any] = {"results": selectors.charge_code_picker(kind, service)}
    if kind == "base" and service:
        # DEF-RAT-8752 — the read-only Minimum beside each size on step 2
        # (image 51) is the SERVICE's schedules', known before a code is the
        # service's base. `{}` for a service nobody has set up.
        body["size_minimums"] = selectors.service_size_minimums(service_code=service)
    return Response(body)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AnyTenantRole])
def charge_item(request: Any, charge_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        payload = _payload(request)
        if set(payload) == {"active"}:  # row action: deactivate / reactivate (IS-1)
            return Response(
                services.set_charge_active(_actor(request), charge_id, bool(payload["active"]))
            )
        return Response(services.update_charge(_actor(request), charge_id, payload))
    if request.method == "DELETE":
        services.delete_charge(_actor(request), charge_id)
        return Response(status=204)
    # CR-156-BRC10 — the detail read adds the tiles and the price versions.
    return Response(selectors.charge_detail(selectors.charge_or_404(charge_id)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def charge_plans(request: Any, charge_id: str) -> Response:
    """`CR-087` · `CHG-01`'s Plans tab — WHICH plans this charge code reaches.

    The tab rendered one sentence saying it could not answer: *"The tile above
    counts the plans that carry this definition. Naming them one by one needs a
    read that does not exist yet."* This is that read. **PO ruling 2026-09-10,
    verbatim, asked whether the empty tab bodies should exist at all:
    *"build"*.**

    ⚠ **AND THE TILE IT SAT UNDER WAS UNDERCOUNTING.** `charge_used_by` counts
    `plan_charge_rules` only, so a code that is every water size's BASE — reached
    through `BR-RAT-088` rather than through an attachment — reads `0` while it
    prices every connection on the service. `selectors.charge_reach_plan_ids`
    returns both routes and this endpoint serves both, each row naming which one
    it is on (`DEF-RAT-4832`).

    ⚠ **THE PAGINATION IS THE POINT, NOT THE PLUMBING (`NFR-3`).** The paginator
    is handed the QUERYSET, so `count` is a SQL `COUNT` over the whole set and
    the page is a SQL `LIMIT`/`OFFSET`; only the page's plans are then enriched.
    A code carried by every plan of a 40,000-account tenant is exactly the list
    `NFR-3` exists for, and nothing here caps anything (`NFR-5`).

    ⚠ **NO FILTERS, NO SORT, DELIBERATELY** — the same posture `plan_units`
    takes one screen across. The frame draws one table with no toolbar;
    `BR-SHL-011`'s grammar admits `page` and `per`, which the paginator reads,
    and an undeclared param is ignored rather than erroring.
    """
    require_tenant(request)
    charge = selectors.charge_or_404(charge_id)  # another tenant's code is a 404
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.charge_reach_queryset(charge), request)
    return paginator.get_paginated_response(
        selectors.charge_reach_rows(charge, list(page or []))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def charge_deactivate(request: Any, charge_id: str) -> Response:
    require_tenant(request)
    return Response(services.set_charge_active(_actor(request), charge_id, False))


# ── S9 Taxes & fees tab + S13 form ──────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def taxes(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        payload = _payload(request)
        # CR-013 part 4 step 4's THREE outcomes are ONE save plus two facts, and
        # this is where they separate (DEF-387). `draft: true` creates a tax
        # nobody has put into force — it reads **Draft** and prices nothing;
        # omitted, the tax is activated exactly as every POST /taxes always has,
        # so no existing caller and no seeded rate changes behaviour. *Save &
        # schedule* is this call with a future `effective_from`, which reads
        # **Scheduled**; there is no third code path because there is no third
        # act.
        # CR-165 §9 (`DEF-RAT-9275`) — the redesigned form sends `as_draft:
        # true`; the older `draft: true` is still read so no caller breaks.
        as_draft = bool(payload.pop("as_draft", False)) | bool(payload.pop("draft", False))
        tax = services.create_tax(_actor(request), payload, as_draft=as_draft)
        return _created(request, tax, f"/taxes/{tax['id']}")
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.TAX_SORTS,
        default_sort=selectors.TAX_DEFAULT_SORT,
        allowed_filters=selectors.TAX_FILTERS,
    )
    # CR-165 §9 — the *Over 20%* banner's count, over the whole filtered set.
    return _prepaged(
        request,
        params,
        selectors.tax_page,
        extra={"over_20_count": selectors.tax_over_20_count(params)},
    )


@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])
def tax_item(request: Any, tax_id: str) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        payload = _payload(request)
        if set(payload) == {"active"}:
            return Response(
                services.set_tax_active(_actor(request), tax_id, bool(payload["active"]))
            )
        return Response(services.update_tax(_actor(request), tax_id, payload))
    # CR-165 §9 — the details read carries `premises_reached`/`premises_total`.
    return Response(selectors.tax_read_row(selectors.tax_or_404(tax_id)))


# ── CR-165-BRC10 round 2 · §9 — the redesigned tax screens' new doors ────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def tax_form_options(request: Any) -> Response:
    """Every list the New tax form renders — boundaries (only those that bill
    today), the six due-date rules, the four computation forms and the filing
    frequencies — so no screen hard-codes a choice the engine cannot honour."""
    require_tenant(request)
    return Response(selectors.tax_form_options())


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def tax_new_rate(request: Any, tax_id: str) -> Response:
    """*New rate from a date* (`DEF-RAT-9283`): ends the live version the day
    before `effective_from` and creates the next one, in ONE transaction. 201
    with the new version, like a correction."""
    require_tenant(request)
    created = services.new_tax_rate(_actor(request), tax_id, _payload(request))
    return _created(request, created, f"/taxes/{created['id']}")


@api_view(["PATCH"])
@permission_classes([SystemAdminOnly])
def tax_gl_account(request: Any, tax_id: str) -> Response:
    """Settings › Accounting's door to a tax's liability account — the only
    one after creation (PO 2026-10-03 on CR-008). `{"liability_gl_account_id":
    uuid | null}`. `PATCH /taxes/{id}` refuses the field on a live tax."""
    require_tenant(request)
    return Response(
        services.set_tax_liability_account(_actor(request), tax_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def tax_retire(request: Any, tax_id: str) -> Response:
    """*Retire* — ends the window on `effective_to`; never `deleted_at`."""
    require_tenant(request)
    return Response(services.retire_tax(_actor(request), tax_id, _payload(request)))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def tax_audit(request: Any, tax_id: str) -> Response:
    """Every change to this tax and every version of it, newest first, paged
    (NFR-3): `{at, actor, action, before, after, reason}`. A window onto
    `audit_log` (pruned on retention — hard rule 4), read through rating's
    seam onto the audit module's one query."""
    require_tenant(request)
    tax = selectors.tax_or_404(tax_id)  # another tenant's id is a 404
    paginator = StandardPagination()
    page = list(
        paginator.paginate_queryset(
            seams.tax_audit_queryset(selectors.tax_chain_ids(tax)), request
        )
        or []
    )
    actors = seams.audit_actor_payloads(page)
    return paginator.get_paginated_response(
        [selectors.tax_audit_entry(row, actor) for row, actor in zip(page, actors)]
    )


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def authority_accounts(request: Any) -> Response:
    """Settings › Accounting › Authority accounts (CR-165 §7 item 1)."""
    require_tenant(request)
    if request.method == "POST":
        # The service carries `@require_role(SYSTEM_ADMIN)`, exactly as
        # `POST /taxes` relies on `create_tax`'s.
        row = services.create_authority_account(_actor(request), _payload(request))
        return _created(request, row, f"/settings/authority-accounts/{row['id']}")
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.AUTHORITY_ACCOUNT_SORTS,
        default_sort=selectors.AUTHORITY_ACCOUNT_DEFAULT_SORT,
        allowed_filters=selectors.AUTHORITY_ACCOUNT_FILTERS,
    )
    return _prepaged(request, params, selectors.authority_account_page)


@api_view(["PATCH"])
@permission_classes([SystemAdminOnly])
def authority_account_item(request: Any, account_id: str) -> Response:
    require_tenant(request)
    return Response(
        services.update_authority_account(_actor(request), account_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def tax_deactivate(request: Any, tax_id: str) -> Response:
    require_tenant(request)
    return Response(services.set_tax_active(_actor(request), tax_id, False))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def tax_activate(request: Any, tax_id: str) -> Response:
    """DEF-387 — put a DRAFT into force, optionally on a future statutory date.

    Part 4 step 4's *Activate* and *Save & schedule*. The date is the only
    difference between them, so there is one route and one service.
    """
    require_tenant(request)
    payload = _payload(request)
    return Response(
        services.activate_tax(_actor(request), tax_id, payload.get("effective_from"))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def tax_corrections(request: Any, tax_id: str) -> Response:
    """DEF-384 — *"a documented correction version with a reason"*, at last.

    The door `PATCH /taxes/{id}` now names when it refuses a rate-history edit
    on a live tax. It was refused on the client and nowhere else, and there was
    nothing to send the operator to; both halves are here.

    201, not 200: a correction CREATES a row (the corrected one is superseded,
    never rewritten), and the Location header points at the new rate so a client
    can read what is now in force.
    """
    require_tenant(request)
    correction = services.correct_tax(_actor(request), tax_id, _payload(request))
    return _created(request, correction, f"/taxes/{correction['id']}")


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def tax_matched_premises(request: Any) -> Response:
    """DEF-380 — *"the matched premise count so a wrong boundary is visible
    before rates are entered"*.

    A GET taking the SCOPE itself, not a tax id, because the moment the
    safeguard has to work is TAX-02 step 1: nothing is saved yet and no rate has
    been typed. That is the whole point of the sentence — *before rates are
    entered*. Reading a saved tax's scope is the same call with its two stored
    values, which is what the tax's own page reads.

    ── ⚠ IT TOOK THE BOUNDARY AND NOTHING ELSE UNTIL CR-087 (`PRB-05`) ────────
    A tax states three restrictions and this read honoured one, so a levy
    restricted to Commercial customers on Water reported EVERY premises in the
    utility. That is the one way this safeguard can mislead rather than fail:
    the number is larger than the truth, on the control whose entire job is to
    be smaller than the total when something is wrong. Both other restrictions
    are passed through now, and the count runs the engine's own predicate over
    all three (BR-RAT-107).

    ⚠ **NFR-3 — THIS READ RETURNS A COUNT AND A THREE-LINE SAMPLE.** It must
    never grow into a list of the premises it counted; a list of a T5 tenant's
    40,000 addresses is exactly the unpaginated read that rule forbids.
    """
    require_tenant(request)
    return Response(
        selectors.matched_premises(
            request.query_params.get("premises_scope_kind"),
            request.query_params.get("premises_scope_value"),
            customer_classes=matched_premises_filter_list(
                request.query_params.getlist("customer_classes")
            ),
            services=matched_premises_filter_list(request.query_params.getlist("services")),
        )
    )


def matched_premises_filter_list(values: Any) -> tuple[str, ...]:
    """One query parameter's repeated or comma-joined values, as codes.

    ⚠ **BOTH SPELLINGS, AND READING ONLY ONE IS A SILENT UNNARROWING.** A
    tick-list sends `?customer_classes=a&customer_classes=b`; a hand-typed URL
    and every worked example in the blueprint send `?customer_classes=a,b`. A
    reader that understood one of them would leave the other caller's count at
    the boundary's figure with nothing raising — which is the defect this whole
    task exists to close, one layer down.

    ⚠ **AN ABSENT PARAMETER IS NOT AN EMPTY RESTRICTION.** `()` means *this tax
    restricts nothing on this axis*, and `selectors.matched_premises` reads it
    that way; there is no spelling here for *restricted to no class*, because a
    tax that reaches nobody by construction is not a thing a clerk can type.

    Unknown codes are passed through UNTOUCHED rather than dropped: the engine's
    own gate answers *no* for a class this utility does not use, which is the
    honest count. Silently discarding an unknown code would widen the tax back
    to everybody — the direction that over-charges (BR-RAT-108's own reasoning
    for refusing rather than dropping).
    """
    codes: list[str] = []
    for raw in values or []:
        for part in str(raw).split(","):
            code = part.strip()
            if code and code not in codes:
                codes.append(code)
    return tuple(codes)


# ── The tax detail's Plans and Audit tabs (CR-087, PO ruling 2026-09-10) ────
#
# **PO, verbatim, 2026-09-10: *"build"*** — asked whether the `Plans` and
# `Audit` tabs on the Taxes & fees detail page should exist at all, given the
# blueprint specifies them across four pages and marks them NO COMMITMENT.
# Both tabs rendered ONE SENTENCE saying they could not do their job, and the
# blueprint quotes both of those sentences back as the defect.
#
# Two GETs rather than two more fields on `GET /taxes/{id}`: that row read
# serves the LIST as well, so a `plans` array on it would fetch a plan set and
# a unit count per row of the catalogue — `NFR-3`'s shape one layer down.
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def tax_plans(request: Any, tax_id: str) -> Response:
    """WHICH plans carry this tax, and HOW each one gets it.

    The tile above it has always counted them (`used_by_plans`); this names
    them and says, per plan, whether the tax arrives through the authority the
    plan binds or through an attachment somebody made on the plan — the two
    mechanisms `BR-RAT-113` gives, which behave differently when the authority
    changes.
    """
    require_tenant(request)
    return Response(selectors.tax_plans(tax_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def tax_versions(request: Any, tax_id: str) -> Response:
    """THIS TAX'S OWN DATED ROWS, newest first — what the rate has been.

    ⚠ **IT IS THE OBJECT'S OWN CHAIN AND NEVER A FILTERED `audit_log` QUERY.**
    The two are both append-only histories of the same object and they answer
    different questions: a version row is a priced state bills still resolve
    to, an audit row is an actor + action + timestamp the engine never reads —
    and `audit_log` is PRUNED on a retention schedule (hard rule 4's
    2026-09-02 narrowing), so a rate history sourced from it loses its authors
    with nothing raising.
    """
    require_tenant(request)
    return Response(selectors.tax_correction_chain(tax_id))


# ── The exemption object: categories and certificates (DEF-383) ─────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def tax_exemption_categories(request: Any, tax_id: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        category = services.create_exemption_category(_actor(request), tax_id, _payload(request))
        return _created(request, category, f"/taxes/{tax_id}/exemption-categories")
    selectors.tax_or_404(tax_id)  # 404 for another tenant's id, before any read
    return Response(selectors.exemption_categories_for_tax(tax_id))


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def tax_exemption_certificates(request: Any, category_id: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        # A4 `plans_rates`: a Billing Clerk is View here. The service admits a
        # clerk since the 2026-10-05 ruling (a certificate recorded at move-in,
        # the ACCOUNT side, where A4 gives Full); this door stays System Admin's.
        if getattr(request, "tenant_role", None) != SYSTEM_ADMIN:
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-SHL-025")
        certificate = services.record_exemption_certificate(
            _actor(request), category_id, _payload(request)
        )
        return _created(request, certificate, f"/exemption-categories/{category_id}/certificates")
    selectors.exemption_category_or_404(category_id)
    return Response(selectors.exemption_certificates_for_category(category_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def exemption_certificate_revoke(request: Any, certificate_id: str) -> Response:
    """Withdraw a claim now. Revoked, never deleted — see the service."""
    require_tenant(request)
    return Response(services.revoke_exemption_certificate(_actor(request), certificate_id))


# ── S9 Discounts tab + the discount definition detail (CR-013 part 3) ───────
#
# ⚠ THESE TWO HANDLERS ARE WHY THE SIX DISCOUNT TABLES ARE NOW REACHABLE.
# `0009_cr013_discounts.py` created them on 2026-08-19 with every write service,
# every rule and the R6 pricing door built and tested — and this file served 18
# handlers, none of them a discount, so a person could not see one row. Hard-won
# law 2: built is not wired.
#
# ⚠ **THE WRITE HALF ARRIVED WITH ITS SCREEN, 2026-08-21, AND THAT SEQUENCING WAS
# THE POINT.** This block used to read *"GET ONLY, AND THE ABSENCE OF A WRITE IS
# THE DECISION … exposing a POST here without the wizard would be a create path
# with no screen, which is the same defect from the other end."* DIS-02 (§18 row
# 12) is now `07-frontend/src/features/rating/DiscountWizard.tsx`, so the
# condition that sentence named is met and the two write routes below mount.
#
# ⚠ **THEY ADD NO RULE AND NO ARITHMETIC.** Every gate, every refusal and every
# money decision belongs to `discount_services`, which is 🔒 HUMAN-REVIEW-PENDING
# and is NOT edited by this lane — including DEF-388, whose one-line fix is the
# write lane's (a `named_codes` scope is refused on the very field that supplies
# it, so the wizard offers the scope and states the gap on the control). These
# handlers are `require_tenant` + delegate, the shape every other write on this
# file already has.
#
# ⚠ **EDITING WHAT A DISCOUNT IS WORTH IS NOT A PATCH, AND THAT HALF IS
# UNCHANGED.** BR-RAT-078 makes enrolments survive versioning and CR-013's
# shared rules make a change to the priced agreement a NEW DATED VERSION
# (`create_discount_version`, which requires a `change_reason`). Nothing below
# opens a path around that.
#
# ⚠ **THIS BLOCK READ *"There is no `update_discount` anywhere in the module and
# that is deliberate"* UNTIL 2026-09-17, AND IT WAS TRUE AND COSTLY AT THE SAME
# TIME (`DEF-RAT-5709`, `BR-RAT-1016`).** The rule it stated covers the priced
# agreement; the SENTENCE covered the whole object, so the discount was the one
# priced object of five with no edit path of ANY kind — a clerk could not fix a
# misspelt programme name, and could not fix a typo in a DRAFT version nobody
# had submitted, which had priced nothing and which `correct_tax` next door
# edits freely for exactly that reason. The only route out of either was a
# second version through submit, approve and activate.
#
# **THREE DOORS NOW, AND EACH IS NARROWER THAN THE ONE THE RULE FORBIDS:**
# `PATCH /discounts/{id}` writes the IDENTITY only — code, name, programme
# owner, funding source, the assistance-filing flag — which is what the
# programme is CALLED and who runs it, the same class of fact as the GL account
# below and never part of the priced agreement. `PATCH
# /discounts/{id}/versions/{vid}` edits a DRAFT that has never been submitted.
# `POST /discounts/{id}/versions/{vid}/corrections` restates a LIVE version over
# the SAME window when the figure recorded was wrong. What is worth what, from
# when, still goes through `POST /discounts/{id}/versions`.
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # POST is System-Admin-gated in the service
def discounts(request: Any) -> Response:
    """DIS-01: Code · Discount · Type · Value · Eligibility · Verification ·
    Plans · Enrolled · Status. Staff read (A4 gives Clerk and Executive View);
    the POST is DIS-02's commit and lands a DRAFT discount with version 1."""
    require_tenant(request)
    if request.method == "POST":
        discount = discount_services.create_discount(_actor(request), _payload(request))
        return _created(request, discount, f"/discounts/{discount['id']}")
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.DISCOUNT_SORTS,
        default_sort=selectors.DISCOUNT_DEFAULT_SORT,
        allowed_filters=selectors.DISCOUNT_FILTERS,
    )
    return _prepaged(request, params, selectors.discount_page)


@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])  # PATCH is System-Admin-gated in the service
def discount_item(request: Any, discount_id: str) -> Response:
    """ONE discount — the read behind `CHG-01.discount` (BR-RAT-084, §18 row 11).

    ⚠ It serves **counts, never people**: no enrolment row, no account id and no
    document reaches this payload, so BR-RAT-079's restricted income and medical
    proof cannot leak through a list that forgot to filter.
    """
    require_tenant(request)
    if request.method == "PATCH":
        # `CR-166` §9 — *Name and details*, saved on THIS version: the identity
        # plus the version's non-priced details; value, limits and start are
        # refused by name on a live discount (`update_discount_details`).
        selectors.discount_or_404(discount_id)
        return Response(
            discount_services.update_discount_details(
                _actor(request), discount_id, _payload(request)
            )
        )
    return Response(selectors.discount_detail(discount_id))


@api_view(["PATCH"])
@permission_classes([SystemAdminOnly])
def discount_gl_account(request: Any, discount_id: str) -> Response:
    """CR-066 B3 — where this discount posts. `{"gl_account_id": uuid | null}`.

    ⚠ **THE OBJECT ROUTE STAYS READ-ONLY AND THIS IS NOT A CRACK IN THAT.** The
    block above says an edit to a discount is a NEW DATED VERSION and never a
    PATCH, because BR-RAT-078 makes enrolments survive versioning. **A GL
    account is not part of the priced agreement**: it moves no money, changes no
    customer's reduction, and is the same kind of fact as
    `charges.gl_account_id` two screens over — a mapping a bookkeeper re-points
    on Settings → Accounting. So it gets its own narrow door, named for exactly
    the one field it writes, and the versioned door remains the only way to
    change what a discount is WORTH.

    The refusals and the audit row belong to `services.set_discount_gl_account`;
    this is `require_tenant` + delegate, the shape every other write here has.
    """
    require_tenant(request)
    return Response(
        services.set_discount_gl_account(_actor(request), discount_id, _payload(request))
    )


@api_view(["GET", "POST"])
@permission_classes([SystemAdminOnly])
def discount_versions(request: Any, discount_id: str) -> Response:
    """GET · this discount's own dated rows, newest first. POST · a new one.

    ⚠ **THE `GET` IS `DEF-RAT-5817` AND IT IS HALF THE FIX.** The POST below
    refuses a second draft in words; a refusal that says *finish it or discard
    it* is only actionable if the clerk can SEE the draft, and until this read
    they could not — DIS-02's Audit tab rendered the stated absence *"no
    endpoint serves those versions yet"* and the detail header went on saying
    `V1` while a `V2` draft blocked every further edit.

    ⚠ **THE OBJECT'S OWN VERSION TABLE, NEVER A FILTERED `audit_log` QUERY** —
    `tax_versions` above states the reason in full and it is unchanged here.

    DIS-02 opened on a stored discount — a NEW DATED VERSION, never an edit.

    Same shape as `rate_schedule_versions` above and for the same reason
    (BR-RAT-037's append-only discipline, BR-RAT-078's *"enrolments survive
    versioning"*). The service requires a `change_reason` on every version after
    the first, so a history where every row says nothing is unwritable.
    """
    require_tenant(request)
    if request.method == "GET":
        discount = selectors.discount_or_404(discount_id)
        return Response(discount_services.discount_version_chain(discount))
    version = discount_services.create_discount_version(
        _actor(request), discount_id, _payload(request)
    )
    return _created(request, version, f"/discounts/{discount_id}")


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_version_discard(request: Any, discount_id: str, version_id: str) -> Response:
    """`DEF-RAT-5817` — throw a parked DRAFT away, so the edit door reopens.

    A `POST` to a named act and not a `DELETE` on the version, which is the
    shape `discard_rate_schedule_draft` already uses for the identical index on
    `tariff_versions`: what is being asked for is *discard this draft*, an act
    the service audits, rather than *remove this row*. The nesting is CHECKED —
    `discount_version_or_404` resolves the pair, so a version id belonging to
    another discount refuses instead of discarding it.
    """
    require_tenant(request)
    selectors.discount_version_or_404(discount_id, version_id)
    return Response(
        discount_services.discard_discount_version_draft(_actor(request), version_id)
    )


# ── The three lifecycle acts (DEF-400) ──────────────────────────────────────
#
# ⚠ **A DISCOUNT COULD BE CREATED AND COULD NEVER GO LIVE.** `submit`, `approve`
# and `activate` landed in `discount_services` on 2026-08-19 with 47 passing
# tests, the read API on 2026-08-21 morning and the write API and the wizard the
# same afternoon — and every one of those lanes correctly built its own slice, so
# the status column said `Draft` forever and BR-RAT-083's *"anyone may DRAFT,
# Owner/Admin ACTIVATE"* was implemented exactly half. Hard-won law 2 with a
# backend shape G13 has no equivalent for: three `@require_role` write functions
# that no `path()` in this file reached.
#
# ⚠ **THEY ADD NO RULE, AND ON THIS BLOCK THAT SENTENCE IS LOAD-BEARING.** The
# second-approval requirement is computed at SUBMIT and STORED with the threshold
# that decided it (BR-RAT-077, `$50,000` by PO ruling 2026-08-21, measured
# against the discount's OWN budget cap, and a discount with NO budget cap
# ALWAYS requires it). Nothing here recomputes it, because an approver must see
# the requirement the submitter saw and a tenant that edits the threshold in
# between would otherwise move the bar under a signature already given. A
# submitter MAY approve their own filing (PO 2026-08-19, *"yes allow it"* — a
# 1–2 staff utility often has no second person) and the service records the fact
# on the row and in its own audit action, so an auditor reads it rather than
# inferring it from two matching ids.
#
# ⚠ **THE NESTING IS CHECKED, NOT DECORATIVE.** Each handler resolves the pair
# through `selectors.discount_version_or_404` before delegating, so
# `/discounts/{someone-elses-id}/versions/{vid}/approve` refuses instead of
# approving the version the second id names.
#
# ⚠ **AND ACTIVATION IS OFFERED FROM `scheduled` ONLY BY THE PRODUCT, WHILE THE
# SERVICE ALSO ACCEPTS `draft` — REPORTED AS DEF-406, NOT PAPERED OVER HERE.**
# This file holds no rules, so it does not narrow the service; the screen offers
# Activate only on an approved version, which is why mounting the route does not
# open a path around the second approval today.
@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_version_submit(request: Any, discount_id: str, version_id: str) -> Response:
    """Submit a DRAFT version for approval — and submitting FREEZES it (§A7.2).

    This is the call BR-RAT-077 hangs off: the requirement and the threshold that
    decided it are written onto the row HERE and read unchanged at approval.
    """
    require_tenant(request)
    selectors.discount_version_or_404(discount_id, version_id)
    return Response(discount_services.submit_discount_version(_actor(request), version_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_version_approve(request: Any, discount_id: str, version_id: str) -> Response:
    """Approve a pending version. The gate is unchanged — activation still needs
    an approval ACT — and a self-approval is recorded rather than refused."""
    require_tenant(request)
    selectors.discount_version_or_404(discount_id, version_id)
    return Response(discount_services.approve_discount_version(_actor(request), version_id))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_version_activate(request: Any, discount_id: str, version_id: str) -> Response:
    """Make an approved version the one in force, superseding its predecessor —
    and lift the DISCOUNT itself out of `draft` (BR-RAT-072's four statuses).

    The service refuses a type no engine can price here rather than at bill time
    (BR-RAT-068), which is why this is the act that can fail on a version that
    saved cleanly.
    """
    require_tenant(request)
    selectors.discount_version_or_404(discount_id, version_id)
    return Response(discount_services.activate_discount_version(_actor(request), version_id))


@api_view(["PATCH"])
@permission_classes([SystemAdminOnly])
def discount_version_item(request: Any, discount_id: str, version_id: str) -> Response:
    """`BR-RAT-1016` verb 1 — edit a DRAFT version that has never been submitted.

    A draft has priced nothing, so there is nothing to preserve and nothing to
    explain: no reason, no version bump, no approval. The service refuses on any
    other status and NAMES the correction route in its refusal, so the road does
    not end where a clerk is standing.
    """
    require_tenant(request)
    selectors.discount_version_or_404(discount_id, version_id)
    return Response(
        discount_services.update_discount_version(_actor(request), version_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_version_corrections(request: Any, discount_id: str, version_id: str) -> Response:
    """`BR-RAT-1016` verb 2 — correct a LIVE version over the SAME window.

    ⚠ **IT IS A POST TO A COLLECTION AND NOT A PATCH, AND THE SHAPE IS THE
    RULE.** A correction MINTS a row; the corrected version is never rewritten.
    The same spelling `POST /taxes/{id}/corrections` already uses, because two
    objects answering the same question must not answer it two ways.
    """
    require_tenant(request)
    selectors.discount_version_or_404(discount_id, version_id)
    return Response(
        discount_services.correct_discount_version(
            _actor(request), version_id, _payload(request)
        )
    )


# ── CR-166-BRC10 §9 · the redesigned discount screens' doors ────────────────
#
# Each is `require_tenant` + delegate; every rule, refusal and audit row is the
# service's (`discount_services`) and every read the selector's
# (`discount_reads`). Lifecycle acts are addressed to THE DISCOUNT, because the
# drawing's buttons are (PO rulings of 2026-10-03: approval is the last act and
# there is no Activate; Retire takes a date).
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def discount_form_options(request: Any) -> Response:
    """Every list the New discount form renders — the utility's own program
    owners, exclusivity groups and who-qualifies values (Settings › Reference
    data) and the fixed vocabularies — plus the utility's currency."""
    require_tenant(request)
    return Response(discount_reads.form_options())


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_submit(request: Any, discount_id: str) -> Response:
    """The discount's draft goes for approval (and is frozen — §A7.2)."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    return Response(
        discount_services.submit_discount(_actor(request), discount_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_approve(request: Any, discount_id: str) -> Response:
    """Approve — the LAST act: the version goes live by itself on its start
    date (PO ruling 2026-10-03 (1))."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    return Response(
        discount_services.approve_discount(_actor(request), discount_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_send_back(request: Any, discount_id: str) -> Response:
    """`{note}` — the approver returns the filing to draft, with a note."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    return Response(
        discount_services.send_back_discount(_actor(request), discount_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_new_value(request: Any, discount_id: str) -> Response:
    """*New value from a date* — the live version ends the day before. 201."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    created = discount_services.new_discount_value(_actor(request), discount_id, _payload(request))
    return _created(request, created, f"/discounts/{discount_id}")


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_corrections(request: Any, discount_id: str) -> Response:
    """*Fix a mistake* — same window, reason required, old row kept."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    return Response(
        discount_services.correct_discount(_actor(request), discount_id, _payload(request))
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_retire(request: Any, discount_id: str) -> Response:
    """`{effective_to}` — after that date nobody gets it, enrolled accounts
    included; nothing changes before it (PO ruling 2026-10-03 (4))."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    return Response(
        discount_services.retire_discount(_actor(request), discount_id, _payload(request))
    )


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # POST is System-Admin-gated in the service
def discount_plans(request: Any, discount_id: str) -> Response:
    """The plans that offer it, each with its `units` and `accounts`, paged.

    `POST {plan, reason}` — `DEF-478`: *+ Add to a plan* on the discount's own
    page; the plan offers it from today (`services.add_discount_to_plan`)."""
    require_tenant(request)
    discount = selectors.discount_or_404(discount_id)
    if request.method == "POST":
        return Response(
            services.add_discount_to_plan(_actor(request), discount.id, _payload(request)),
            status=201,
        )
    params = parse_list_params(request.query_params, allowed_sorts=(), allowed_filters=())
    return _prepaged(
        request,
        params,
        lambda p: selectors._sql_page(
            discount_reads.discount_plans_queryset(discount), p, discount_reads.discount_plan_rows
        ),
    )


@api_view(["DELETE"])
@permission_classes([AnyTenantRole])  # System-Admin-gated in the service
def discount_plan_item(request: Any, discount_id: str, plan_id: str) -> Response:
    """`DELETE {reason}` — `DEF-478`: × on a Plans-tab row. Ruling 2: the
    binding ends yesterday and so do the enrolments of accounts on that plan
    (`services.remove_discount_from_plan`)."""
    require_tenant(request)
    discount = selectors.discount_or_404(discount_id)
    return Response(
        services.remove_discount_from_plan(
            _actor(request), discount.id, plan_id, _payload(request) or None
        )
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # System-Admin-gated in the service
def discount_duplicate(request: Any, discount_id: str) -> Response:
    """`{code, name}` — `DEF-RAT-9310`: a NEW DRAFT discount copied from the
    version in force (`discount_services.duplicate_discount`)."""
    require_tenant(request)
    selectors.discount_or_404(discount_id)
    row = discount_services.duplicate_discount(_actor(request), discount_id, _payload(request))
    return _created(request, row, f"/discounts/{row['id']}")


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([JSONRenderer, _CsvFormat])
def discount_accounts(request: Any, discount_id: str) -> Response:
    """The Accounts tab — who receives it, paged, searched and filtered in SQL
    (`f.status`, `f.plan`, `q`). BR-RAT-079: a proof document is served to a
    System Admin only, as the account document's id (`DEF-CUS-9780`).

    `?format=csv` (`DEF-1005`) streams the WHOLE filtered set, 500 rows a read
    — no page, no cap (NFR-3, NFR-5)."""
    require_tenant(request)
    discount = selectors.discount_or_404(discount_id)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=discount_reads.ACCOUNT_SORTS,
        default_sort=discount_reads.ACCOUNT_DEFAULT_SORT,
        allowed_filters=discount_reads.ACCOUNT_FILTERS,
    )
    if request.query_params.get("format") == "csv":
        return _csv_response(
            discount_reads.discount_accounts_csv(discount, params),
            f"discount-{discount.code.lower()}-accounts.csv",
        )
    # DEF-CUS-9780 — the proof on an enrolment is the VERIFIER's to see: a
    # System Admin gets `proof_document_id` (the account document to open),
    # every other role reads null (BR-RAT-079: proof is restricted by role).
    verifier = getattr(request, "tenant_role", None) == SYSTEM_ADMIN

    def rows(enrolments: list[Any]) -> list[dict[str, Any]]:
        built = discount_reads.discount_account_rows(enrolments)
        proofs = (
            discount_services.enrolment_proof_references([row["enrolment_id"] for row in built])
            if verifier
            else {}
        )
        for row in built:
            row["proof_document_id"] = proofs.get(row["enrolment_id"])
        return built

    return _prepaged(
        request,
        params,
        lambda p: selectors._sql_page(
            discount_reads.discount_accounts_queryset(discount, p),
            p,
            rows,
        ),
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
@renderer_classes([JSONRenderer, _CsvFormat])
def discount_audit(request: Any, discount_id: str) -> Response:
    """Every change to the discount, its versions, its plan links and its
    enrollments, newest first, paged: `{at, actor, action, before, after,
    reason}`, names not ids. A window onto `audit_log`, which is pruned on
    retention (hard rule 4) — the screen claims no permanence.

    `?format=csv` (`DEF-1005`) streams every row, 500 a read (NFR-3, no cap)."""
    require_tenant(request)
    discount = selectors.discount_or_404(discount_id)
    if request.query_params.get("format") == "csv":
        return _csv_response(
            discount_reads.discount_audit_csv(discount),
            f"discount-{discount.code.lower()}-audit.csv",
        )
    paginator = StandardPagination()
    page = list(
        paginator.paginate_queryset(
            seams.discount_audit_queryset(discount_reads.discount_audit_filter(discount)),
            request,
        )
        or []
    )
    actors = seams.audit_actor_payloads(page)
    return paginator.get_paginated_response(discount_reads.discount_audit_entries(page, actors))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_enrolment_end(request: Any, enrolment_id: str) -> Response:
    """`{ended_on, reason}` — end ONE enrollment (the Accounts tab's row act)."""
    require_tenant(request)
    payload = _payload(request)
    return Response(
        discount_services.end_enrolment(
            _actor(request),
            enrolment_id,
            reason=str(payload.get("reason") or ""),
            ended_on=payload.get("ended_on"),
        )
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def discount_enrolment_verify(request: Any, enrolment_id: str) -> Response:
    """`{}` — the proof is on file: ONE *Proof pending* enrollment becomes
    *Receiving* (the Accounts tab's row act).

    DEF-RAT-9325 (CR-166 task 9 web walk): `discount_services.verify_enrolment`
    was built and never routed, so an enrollment whose version needs proof
    before the first reduction stayed pending for ever and its bill never
    carried the discount — Senior 15% on a $60.00 bill read $0.00, not −$9.00.
    The service decides everything (the recertification clock, the audit row);
    this view only opens the door."""
    require_tenant(request)
    return Response(discount_services.verify_enrolment(_actor(request), enrolment_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def tax_jurisdictions(request: Any) -> Response:
    """BR-TEN-037: this tenant's own jurisdictions — there is no global registry.

    ⚠ **THIS SERVED A BARE ARRAY UNTIL 2026-09-19 (`DEF-RAT-5754`, `NFR-3`).**
    It was the SEVENTH list read in this module and the one `DEF-RAT-5742`
    could not find: that lane grepped for `_paginated`, which by construction
    cannot see a read that never reached the paginator at all. `core.pagination`
    says an endpoint *"has to go out of its way to be unbounded, and none may"*
    — this one did, by returning the selector's list straight to `Response`.

    ⚠ **IT DOES NOT LOOK LIKE A LIST, WHICH IS WHY IT SURVIVED SIX WEEKS.** It
    feeds the S13 wizard's step-1 PICKER, so it reads as a lookup vocabulary
    rather than as a catalogue — and a vocabulary is the one shape a reader
    forgives for being whole.

    ⚠ **AND THE HONEST SIZE OF IT, BECAUSE OVERSTATING THIS WOULD BE ITS OWN
    DEFECT.** A real tenant holds about **53** jurisdictions (`CR-077` seeds
    `TX`, `ALL` and every US state code), and that number does NOT follow the
    account count — T5's 40,000 is accounts, not jurisdictions. So nothing a
    clerk can see changed today. What changed is that the shape was unbounded:
    no rule, index or code path stopped a utility entering five thousand, and
    nothing would have refused to serve all five thousand in one reply. This is
    `NFR-3` conformance and `NFR-5` read forwards, not a performance rescue.

    ⚠ **THE WIRE SHAPE CHANGED, SO THE CLIENT CHANGED IN THE SAME COMMIT.**
    `TaxJurisdiction[]` became the four-key envelope; `getTaxJurisdictions`
    now follows `count` and the S13 picker still receives every row
    (`BR-SHL-033` — a picker that can only see page 1 would have been a new
    defect, not a fix). Shipping the backend half alone was the whole reason
    `DEF-RAT-5742` left this one open.
    """
    require_tenant(request)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.JURISDICTION_SORTS,
        default_sort=selectors.JURISDICTION_DEFAULT_SORT,
        allowed_filters=selectors.JURISDICTION_FILTERS,
    )
    return _prepaged(request, params, selectors.jurisdiction_page)


# ── S9 History + bulk rate update (EP-RAT-04) ───────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def rate_changes(request: Any) -> Response:
    """POST = the bulk update: validated + previewed synchronously, applied
    asynchronously → 202 + job_id (B12 r1). `{"preview": true}` returns the
    before → after rows with 200 and writes nothing (IS-6)."""
    require_tenant(request)
    if request.method == "POST":
        payload = _payload(request)
        result = services.request_rate_change_batch(_actor(request), payload)
        if payload.get("preview"):
            return Response(result)
        return Response(result, status=202)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=selectors.HISTORY_SORTS,
        default_sort=selectors.HISTORY_DEFAULT_SORT,
        allowed_filters=selectors.HISTORY_FILTERS,
    )
    if "dir" not in request.query_params:  # capability matrix: changed_at DESC
        params = replace(params, dir="desc")
    return _prepaged(request, params, selectors.history_page)


urlpatterns = [
    path("plans", plans),
    # `CR-167-BRC10` §7.3 — BEFORE `plans/<plan_id>`, which would take it.
    path("plans/form-options", plan_form_options),
    path("plans/<str:plan_id>", plan_item),
    path("plans/<str:plan_id>/audit", plan_audit),
    path("plans/<str:plan_id>/versions", plan_versions_create),
    path("plans/<str:plan_id>/versions/<int:version_no>/publish", plan_version_publish),
    path("plans/<str:plan_id>/duplicate", plan_duplicate),  # DEF-RAT-9352
    path("plans/<str:plan_id>/units", plan_units),  # CR-087 D5 · PRB-21
    path("plans/<str:plan_id>/publish", plan_publish),
    path("plans/<str:plan_id>/archive", plan_archive),
    # OQ-RAT-12409 option A · BR-RAT-1016 verb 2 — a correction restates this
    # plan at the SAME version number. The other four priced objects spell it
    # the same way.
    path("plans/<str:plan_id>/corrections", plan_corrections),
    # PO ruling 2026-09-18 — what moved underneath this plan. READ-ONLY, paged
    # from the server, and it writes no plan version (a bound object changing is
    # not a change to the plan).
    path("plans/<str:plan_id>/bound-changes", plan_bound_changes),
    # BR-RAT-113 — PLN-03 step 5's attach / detach row actions.
    path("plans/<str:plan_id>/taxes", plan_taxes),
    path("plans/<str:plan_id>/taxes/<str:tax_id>", plan_tax_item),
    # CR-130-BRC07 — BEFORE the `<str:tariff_id>` patterns, or Django would
    # match this literal as a tariff id and answer 404 for a route that
    # exists. The wizard asks it before any schedule has been saved.
    path("rate-schedules/percent-basis-options", percent_basis_options),
    path("rate-schedules", rate_schedules),
    # ⚠ BEFORE `rate-schedules/<str:tariff_id>`, or it is read as an id.
    path("rate-schedules/base-to-choose", rate_schedules_base_to_choose),  # DEF-RAT-9797
    path("rate-schedules/<str:tariff_id>", rate_schedule_item),
    path("rate-schedules/<str:tariff_id>/activate", rate_schedule_activate),
    path("rate-schedules/<str:tariff_id>/impact", rate_schedule_impact),
    path("rate-schedules/<str:tariff_id>/rates", rate_schedule_rates),  # CR-157-BRC10 B
    path("rate-schedules/<str:tariff_id>/plans", rate_schedule_plans),  # CR-157-BRC10 B
    path("rate-schedules/<str:tariff_id>/versions", rate_schedule_versions),
    path(
        "rate-schedules/<str:tariff_id>/versions/<str:version_id>/corrections",
        rate_schedule_version_corrections,
    ),
    path("rate-schedules/<str:tariff_id>/duplicate", rate_schedule_duplicate),
    path("rate-schedules/<str:tariff_id>/discard-draft", rate_schedule_discard_draft),
    path("rate-schedules/<str:tariff_id>/archive", rate_schedule_archive),
    path("charges", charges),
    # ⚠ BEFORE `charges/<str:charge_id>`, or `picker` is read as an id.
    path("charges/picker", charge_picker),  # CR-156-BRC10 · CHG-02 Add picker
    path("charges/<str:charge_id>", charge_item),
    path("charges/<str:charge_id>/plans", charge_plans),  # CR-087 · CHG-01 Plans tab
    path("charges/<str:charge_id>/deactivate", charge_deactivate),
    path("taxes", taxes),
    # ⚠ BEFORE `taxes/<str:tax_id>`, or the literal segment is swallowed as an
    # id and the wizard's step-1 count 404s on a uuid it never sent.
    path("taxes/matched-premises", tax_matched_premises),
    path("taxes/form-options", tax_form_options),  # CR-165 §9 — before the id route
    path("taxes/<str:tax_id>", tax_item),
    path("taxes/<str:tax_id>/deactivate", tax_deactivate),
    path("taxes/<str:tax_id>/activate", tax_activate),
    path("taxes/<str:tax_id>/corrections", tax_corrections),
    path("taxes/<str:tax_id>/plans", tax_plans),
    path("taxes/<str:tax_id>/versions", tax_versions),
    path("taxes/<str:tax_id>/new-rate", tax_new_rate),  # CR-165 §9
    path("taxes/<str:tax_id>/retire", tax_retire),  # CR-165 §9
    path("taxes/<str:tax_id>/gl-account", tax_gl_account),  # PO 2026-10-03 on CR-008
    path("taxes/<str:tax_id>/audit", tax_audit),  # CR-165 §9
    path("settings/authority-accounts", authority_accounts),  # CR-165 §9
    path("settings/authority-accounts/<str:account_id>", authority_account_item),
    path("taxes/<str:tax_id>/exemption-categories", tax_exemption_categories),
    path("exemption-categories/<str:category_id>/certificates", tax_exemption_certificates),
    path("exemption-certificates/<str:certificate_id>/revoke", exemption_certificate_revoke),
    path("discounts", discounts),
    # CR-166 §9 — BEFORE `discounts/<str:discount_id>`, or `form-options` is
    # read as an id.
    path("discounts/form-options", discount_form_options),
    path("discounts/<str:discount_id>", discount_item),
    path("discounts/<str:discount_id>/submit", discount_submit),  # CR-166 §9
    path("discounts/<str:discount_id>/approve", discount_approve),  # CR-166 §9
    path("discounts/<str:discount_id>/send-back", discount_send_back),  # CR-166 §9
    path("discounts/<str:discount_id>/new-value", discount_new_value),  # CR-166 §9
    path("discounts/<str:discount_id>/corrections", discount_corrections),  # CR-166 §9
    path("discounts/<str:discount_id>/retire", discount_retire),  # CR-166 §9
    path("discounts/<str:discount_id>/plans", discount_plans),  # CR-166 §9 · POST DEF-478
    path("discounts/<str:discount_id>/plans/<str:plan_id>", discount_plan_item),  # DEF-478
    path("discounts/<str:discount_id>/duplicate", discount_duplicate),  # DEF-RAT-9310
    path("discounts/<str:discount_id>/accounts", discount_accounts),  # CR-166 §9
    path("discounts/<str:discount_id>/audit", discount_audit),  # CR-166 §9
    path("discount-enrolments/<str:enrolment_id>/end", discount_enrolment_end),  # CR-166 §9
    path("discount-enrolments/<str:enrolment_id>/verify", discount_enrolment_verify),  # DEF-RAT-9325
    path("discounts/<str:discount_id>/gl-account", discount_gl_account),
    path("discounts/<str:discount_id>/versions", discount_versions),
    path(
        "discounts/<str:discount_id>/versions/<str:version_id>",
        discount_version_item,  # BR-RAT-1016 verb 1
    ),
    path(
        "discounts/<str:discount_id>/versions/<str:version_id>/corrections",
        discount_version_corrections,  # BR-RAT-1016 verb 2
    ),
    path(
        "discounts/<str:discount_id>/versions/<str:version_id>/discard",
        discount_version_discard,
    ),
    path("discounts/<str:discount_id>/versions/<str:version_id>/submit", discount_version_submit),
    path("discounts/<str:discount_id>/versions/<str:version_id>/approve", discount_version_approve),
    path(
        "discounts/<str:discount_id>/versions/<str:version_id>/activate",
        discount_version_activate,
    ),
    path("tax-jurisdictions", tax_jurisdictions),
    path("rate-changes", rate_changes),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-001@6304a38 (story+rules snapshot hash — EP-RAT-01 lead story; co-packets EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
# generated: 2026-08-09 by story-coder v1 (W1 rating feature lane — services/selectors/API) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-09-18 by the DEF-RAT-5742 lane (NFR-3 — every list takes its page in the DATABASE: `_paginated` is replaced by `_prepaged` and each selector splits into `<x>_list_queryset` + `<x>_page(params) -> (rows, total)`. Measured on the six endpoints at 60 / 120 / 240 catalogue rows, page 1: plans 209 / 209 / 209 statements, rate schedules 403 / 403 / 403, charges 152 / 152 / 152, taxes 202 / 202 / 202, discounts 252 / 252 / 252, rate-changes 2 / 2 / 2 — flat, where before each grew with the catalogue. The `<x>_list` functions keep their exact behaviour for exports.py, seed_demo, sample_data and the two published customers seams. THREE DERIVED PREDICATES KEEP THEIR O(tenant) PATH AND ARE NOT RE-IMPLEMENTED IN SQL — f.status/f.service on taxes, f.type/f.verification on discounts, f.structure/f.status and the seven derived sorts on schedules — on DEF-387's own reasoning, each NAMED by an `<x>_list_is_sql_pageable` predicate so the exception can be counted rather than hidden) · AMENDED 2026-09-19 by the DEF-RAT-5754 lane (NFR-3 — `GET /tax-jurisdictions` was the SEVENTH list in this module and the only one with NO pager at all: it returned `selectors.jurisdiction_list()` straight to `Response`, so the wire carried a bare `TaxJurisdiction[]` with no count and nothing bounding a tenant-wide read. DEF-RAT-5742 could not find it because that lane grepped for `_paginated`, which by construction cannot see a read that never reached the paginator. It now parses list params and goes through the SAME `_prepaged`; `jurisdiction_page`/`jurisdiction_list_queryset` are the selector pair. MEASURED on one tenant of 50,000 jurisdictions: before, 50,000 rows in 1 statement on every request; after, 50 rows in 2 statements at page 1, page 40 and page 1,000 alike. THE WIRE SHAPE CHANGED, so `07-frontend/src/api/endpoints.ts::getTaxJurisdictions` changed in the SAME commit and follows `count` — `SearchSelectField` filters client-side and resolves the selected LABEL from the same array, so a one-page picker would have lost the type-ahead past row 50 AND rendered blank when reopening a tax whose jurisdiction sits past row 50. `TaxWizard.tsx` is untouched)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ pytest tests/test_us_rat_*: 85 passed / 14 skipped (11 isolation halves → G5, 3 owned elsewhere — each with a stated reason)✔ · full suite -m 'not golden and not isolation': 564 passed / 0 failed / 9 skipped✔ (365 baseline + the concurrent metering/assets lanes + this one; two transient cross-lane failures seen mid-run in tests/test_us_aud_001_store.py were the assets lane's shared-fixture ordering and cleared on their side — never reachable from test_us_rat_*, which sorts after test_us_aud_*) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane · [DEF-RAT-5742 lane 2026-09-18] ruff✔ · black: objects to these files AND to the UNMODIFIED tip's copies of them, in unrelated places — the local black 26.3.1 runs on Python 3.11 against a py3.14 target and says so; a pre-existing environment mismatch, not this change · pytest tests/test_def_rat_5742_rating_lists_page_in_sql.py 38 passed · pytest tests/test_us_rat_charges_taxes.py 27 passed / 3 skipped (unchanged)
# exceptions: urlpatterns exported but NOT included in config/urls.py (outside territory — one-line include for the wiring lane) · five endpoints beyond 11b §2.4 (DELETE /plans/{id} · POST /rate-schedules/{id}/archive · DELETE /charges/{id} · GET /tax-jurisdictions · GET /rate-changes) each backing a capability-matrix row action or a ratified TC — REPORTED for the A11 addendum · POST /rate-changes needs the BE-07 job store the /jobs lane owns; without it enqueue fails loudly by design (no 202 over a missing record) · [path-tenancy lane 2026-08-10] 201 Location headers are absolute inside the request's tenant prefix (core.tenancy.tenant_path) — `/plans/{id}` is no longer a path a client can follow
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
