# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md A1 · A2
# Rulings:  14-bulk-bill-run-changes.md rows 10–19, 29–35, 43 (PO 2026-09-30)
# Rules:    BR-BIL-005 · BR-BIL-1041 · A4 reads_billing_runs (Executive VIEW)
#           · BR-TEN-003 / HR-1 · NFR-3 (previous runs are paged)
# Tests:    06-backend/tests/test_bulk_run_scope.py
# ───────────────────────────────────────────────────────
"""The bulk bill run's Scope step over HTTP — the preview and the create.

A SEPARATE `urlpatterns`, for the reason every other billing include in
`config/urls.py` gives: `apps/billing/api.py` is the busiest file in the module
and another lane is in it today (hard-won law 11). The POST still lives at
`POST /billing/runs` — one URL is one view in Django — so `api.bill_runs` hands
its POST branch to `create` below and that is the whole of its edit.

⚠ **ROUTE ORDER IS LOAD-BEARING.** `billing/runs/scope-preview` would be
swallowed by `api.py`'s `billing/runs/<str:run_id>` (and answer *run not
found*), so `config/urls.py` includes this module BEFORE `apps.billing.api`.
`tests/test_bulk_run_scope.py` resolves the path through the real root URLconf,
so a reordering goes red.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import run_scope, runs, selectors
from apps.billing.exceptions import BillingRuleError
from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core.pagination import clamp_page_size
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant


def _may_run(request: Any) -> bool:
    """A4: Admin or Clerk start a run; the Executive VIEWS. The same class the
    POST's door uses, asked rather than restated."""
    return bool(AdminOrClerk().has_permission(request, None))


def _check_from(source: Any, *, can_run: bool) -> run_scope.ScopeCheck:
    """The preview and the POST ask the SAME check, so what the screen shows is
    what Start is told. (A TEMPORARY path that derived a missing run name and
    template for the old `BillRunWizard` was removed with it — plan task F2.)"""
    return run_scope.check_scope(
        cycle_id=source.get("cycle_id"),
        period_start=source.get("period_start"),
        period_end=source.get("period_end"),
        bill_date=source.get("bill_date"),
        due_days=source.get("due_days"),
        template_id=source.get("template_id"),
        label=source.get("label"),
        can_run=can_run,
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive View on Reads & Billing runs
def scope_preview(request: Any) -> Response:
    """`GET /billing/runs/scope-preview` — everything the Scope step shows. READ ONLY.

    Takes the same fields the POST takes (`cycle_id`, `period_start`,
    `period_end`, `bill_date`, `due_days`, `template_id`, `label`) and answers
    the refusals and warnings the POST would give, all at once, each on its
    field; the cycle's counts and the previous run's three account counts;
    the cycle's details; continuity; and the cycle's previous runs, PAGED
    (`page`, `per` — NFR-3), newest first, through the one run-list read
    (`selectors.bill_runs_page`) so this panel and screen 27 cannot describe a
    run differently.

    ⚠ **IT WRITES NOTHING** — no run, no number allocated, no audit row. An
    Executive may call it and is told `not_allowed` among the refusals, which is
    the truthful answer to *could I start this*.
    """
    require_tenant(request)
    from apps.billing import api as billing_api  # the envelope helper; api imports this module

    params = request.query_params
    check = _check_from(params, can_run=_may_run(request))
    body = run_scope.preview(check)
    previous_runs = None
    if check.cycle is not None:
        try:
            page = int(str(params.get("page") or 1))
        except (TypeError, ValueError):
            page = 1
        result = selectors.bill_runs_page(
            cycle_id=check.cycle["id"], page=page, per=clamp_page_size(params.get("per"))
        )
        previous_runs = billing_api._page_envelope(request, result)
    body["previous_runs"] = previous_runs
    return Response(body)


def create(request: Any) -> Response:
    """`POST /billing/runs` (A1) — called by `api.bill_runs` for its POST.

    **EVERY refusal at once.** The whole of row 43 is checked BEFORE anything is
    written; any refusal answers with ALL of them in `field_errors`, each on its
    field with its own key, and the warnings in `params.warnings`, so a clerk
    with four mistakes reads four sentences rather than fixing one and pressing
    Start again. No refusal → the run is created and the warnings come back on
    the 201.

    **Run name and template are REQUIRED** (B4 — PO 2026-09-30, *"What to bill
    - in drawring i will give run name"*; BR-BIL-1041). ⚠ **AND `scope_services`
    IS NO LONGER READ** (B3, PO 2026-09-30: *"which servcies to be billed in
    unit /account is decied at run time -so this filter is of now use"*). A
    stale client that still sends it creates a whole-cycle run, which is the
    ruling; it is ignored rather than refused so the live screen's leftover
    checkboxes cannot stop a utility billing.

    The duplicate keeps its old envelope (409 BIZ-IDEMPOTENT, `billing.run.
    duplicate`, `run_id`/`ran_by`/`ran_at`) because screens already read it;
    the other refusals ride beside it in `field_errors`. Every other refusal
    set answers 422 BIZ-COMPLETENESS with `billing.runScope.refused`.
    """
    from apps.billing import api as billing_api

    payload = billing_api._payload(request)
    check = _check_from(payload, can_run=True)
    warnings = [problem.as_dict() for problem in check.warnings]
    if not check.ok:
        field_errors = [problem.as_field_error() for problem in check.refusals]
        duplicate = next(
            (p for p in check.refusals if p.code.startswith("duplicate_run")), None
        )
        if duplicate is not None:
            raise errors.BizError(
                errors.BIZ_IDEMPOTENT,
                br_ref="BR-BIL-005",
                message_key="billing.run.duplicate",
                params={
                    "run_id": duplicate.params.get("run_id"),
                    "ran_by": duplicate.params.get("ran_by"),
                    "ran_at": duplicate.params.get("ranAt"),
                    "count": len(field_errors),
                    "warnings": warnings,
                },
                field_errors=field_errors,
            )
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-1050",
            message_key="billing.runScope.refused",
            params={"count": len(field_errors), "warnings": warnings},
            field_errors=field_errors,
        )

    parsed = check.parsed
    try:
        run = runs.create_run(
            cycle_id=parsed["cycle_id"],
            period_start=parsed["period_start"],
            period_end=parsed["period_end"],
            bill_date=parsed["bill_date"],
            due_days=parsed["due_days"],
            case_defaults=payload.get("case_defaults"),
            label=parsed["label"],
            template_id=parsed["template_id"],
            run_by=billing_api._actor_id(request),
        )
    except runs.DuplicateRun as duplicate:
        # Lost a race between the check and the insert — the unique index is
        # the real guarantee, and the answer is BR-BIL-005's who/when/link.
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-BIL-005",
            message_key="billing.run.duplicate",
            params={
                "run_id": str(duplicate.original.pk),
                "ran_by": (
                    None
                    if duplicate.original.run_by_id is None
                    else str(duplicate.original.run_by_id)
                ),
                "ran_at": duplicate.original.created_at.isoformat(),
            },
        ) from duplicate
    except BillingRuleError as refusal:
        raise billing_api._as_catalog_refusal(refusal, "BR-BIL-005") from refusal
    # `create_run` can only REPORT a missing series; the check above already
    # warned for it, so a second copy is added only if the two disagree (a
    # series deleted between the check and the insert).
    codes = {item["code"] for item in warnings}
    if getattr(run, "numbering_warnings", None) and "no_run_number_series" not in codes:
        warnings.append(run_scope.ScopeProblem("no_run_number_series", None).as_dict())
    return Response({**selectors.run_created_dict(run), "warnings": warnings}, status=201)


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive View on Reads & Billing runs
def scope_list(request: Any) -> Response:
    """`GET /billing/runs/scope-list?cycle_id=&list=nobody|missing_meter` —
    the rows behind Scope's *Nobody to bill* and *Missing meter* counts, PAGED
    (`page`, `per` — NFR-3), in the product's page envelope. READ ONLY
    (DEF-BIL-8221).

    Refusals: no cycle → `billing.runScope.refusal.cycleMissing`; an unknown
    `list` → VAL-005 on `list`; a cycle this tenant cannot see → 404; a module
    that does not answer → SYS-PROVIDER with the preview's own key for it.
    """
    require_tenant(request)
    from apps.billing import api as billing_api  # the envelope helper; api imports this module

    params = request.query_params
    cycle_id = str(params.get("cycle_id") or "").strip()
    which = str(params.get("list") or "").strip()
    field_errors = []
    if not cycle_id:
        field_errors.append(
            {"field": run_scope.FIELD_CYCLE, "code": errors.VAL_REQUIRED,
             "message_key": run_scope.PROBLEMS["cycle_missing"][1]}
        )
    if which not in run_scope.SCOPE_LISTS:
        field_errors.append(
            {"field": "list", "code": errors.VAL_UNKNOWN_LOOKUP,
             "message_key": "billing.runScope.list.unknown"}
        )
    if field_errors:
        raise errors.ValidationError(
            field_errors[0]["code"],
            message_key=field_errors[0]["message_key"],
            field_errors=field_errors,
        )
    try:
        page = int(str(params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        result = run_scope.scope_list(
            cycle_id, which, page=page, per=clamp_page_size(params.get("per"))
        )
    except run_scope._NotAnswering as down:
        code = run_scope._NOT_ANSWERING_CODE.get(down.module, "meter_reads_not_answering")
        raise errors.SysError(
            errors.SYS_PROVIDER,
            message_key=run_scope.PROBLEMS[code][1],
            params={"module": down.module},
        ) from None
    return Response(billing_api._page_envelope(request, result))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive View on Reads & Billing runs
def scope_templates(request: Any) -> Response:
    """`GET /billing/runs/scope-templates` — the bill templates a run may be
    started on (a published version each), PAGED (`page`, `per` — NFR-3).
    READ ONLY (DEF-BIL-8222). *Must be published* stays the POST's refusal."""
    require_tenant(request)
    from apps.billing import api as billing_api  # the envelope helper; api imports this module

    params = request.query_params
    try:
        page = int(str(params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    result = run_scope.run_templates(page=page, per=clamp_page_size(params.get("per")))
    return Response(billing_api._page_envelope(request, result))


urlpatterns = [
    path("billing/runs/scope-preview", scope_preview),
    path("billing/runs/scope-list", scope_list),
    path("billing/runs/scope-templates", scope_templates),
]
