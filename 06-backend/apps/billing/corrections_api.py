# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 (single-bill correction: credit note + rebill with the
#           nine-section impact preview) · US-BIL-016 (bulk corrections: scope
#           selector, staged idempotent execution, per-bill results) ·
#           US-BIL-017 (the approval gate + the correction reason codes as
#           reference data) · US-BIL-031 (document-only correction — the bill is
#           right, the document is wrong)
#           Screens: S30 (Fix a bill tab)
# Rules:    BR-BIL-014 (reason → scope → impact preview → approval → staged
#           idempotent execution → deliver + audit; NO money-bearing write
#           before approval) · BR-BIL-041 (the reason's CLASS derives the
#           mechanism — a caller may never supply one) · BR-BIL-042 (one class
#           per bulk case; a single case takes the strongest present) ·
#           BR-BIL-043 (a D-class case that moves money is REFUSED) ·
#           BR-BIL-044 (the preview is a content-hashed artifact and approval
#           binds it) · BR-BIL-045 (the posting period is named before confirm) ·
#           BR-BIL-046 (the pinned set is a table, not a WHERE clause) ·
#           BR-BIL-047 (abandoning a failure is explicit, reasoned and audited) ·
#           BR-BIL-048 (only the LATEST document in a chain is correctable) ·
#           BR-BIL-004 / HR-4 (the original is never edited — a correction is
#           NEW ROWS) · BR-TEN-043 (event time is an argument, never a clock) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-SHL-020
# Tests:    06-backend/tests/test_us_bil_surface_apis.py ·
#           06-backend/tests/test_cr101_lane_b_scope_resolve.py (`GET
#           /corrections/resolve`, CR-101-BRC03 §06)
# Impacts:  config/urls.py (the include) · apps/billing/selectors.py (the read
#           model) · 07-frontend FixABillPage (S30's Fix a bill tab)
# ───────────────────────────────────────────────────────
"""`/corrections` — the HTTP surface for fixing a bill that is already wrong.

THIN by law (B8/LAW 0): every read goes through `selectors`, every write through
`single_correction` / `bulk_corrections`, no ORM here, and every refusal is a
catalog exception the BE-02 handler renders (G9).

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS
════════════════════════════════════════════════════════════════════════════
The correction engine is 170KB across five modules and every one of them carried
the same deferral in its own Lifecycle trailer: *"no-API-half — the S30
correction endpoints are unbuilt and no correction route is mounted"*. So a
utility that overbilled a customer $19.92 in July had, in a product with a
complete, golden-verified, immutability-enforcing correction engine, **no way to
fix it**. That is hard-won law 2 at the largest scale this module has.

════════════════════════════════════════════════════════════════════════════
THE ONE THING THIS SURFACE WILL NEVER OFFER — AND WHY THE PROTOTYPE IS WRONG
════════════════════════════════════════════════════════════════════════════
`05-prototype/UtilityBilling.html` line 3502 draws four Fix-a-bill choices, and
the fourth is **"Change an amount — Edit specific line items on the bill"**.
That control cannot exist. `invoices` and `invoice_lines` are append-only under
hard rule 4 and the database refuses the UPDATE outright; a screen offering it
would be offering something the storage layer will not do. It is REPORTED as a
prototype divergence rather than ported, and what ships in its place is what
actually happens: pick the reason, read the impact, approve, execute — and the
result is a credit note plus a rebill, both NEW ROWS, with the original intact
and linked.

The prototype's "Cancel this bill" is a VOID (US-BIL-027), which is a different
act with a different rule and no endpoint in this build. It is named on screen
as not-offered-here rather than drawn as a dead control.

════════════════════════════════════════════════════════════════════════════
THE MECHANISM IS NEVER IN THE REQUEST BODY
════════════════════════════════════════════════════════════════════════════
BR-BIL-041 derives the mechanism from the reason's class, and
`correction_reasons.refuse_supplied_mechanism` exists so an attempt has
somewhere to be refused. This surface calls it on every case-opening request:
answering "wrong rate" with a document reprint is a *silent* underbilling — the
customer keeps the wrong amount and no gate anywhere fires — so an API client
that tries to choose is refused rather than obeyed.

════════════════════════════════════════════════════════════════════════════
THE FIVE ROUTES AND THE ONE THAT IS DELIBERATELY NOT HERE
════════════════════════════════════════════════════════════════════════════
    GET  /corrections/reasons        US-BIL-017  the vocabulary + its classes
    GET  /corrections                US-BIL-016  the case list
    POST /corrections                US-BIL-015/016  open a case — PREVIEW ONLY
    GET  /corrections/{id}           US-BIL-015  the nine sections / the panel
    POST /corrections/{id}/approve   US-BIL-017  the gate
    POST /corrections/{id}/execute   US-BIL-015/016/031  the staged job
    POST /corrections/{id}/abandon   BR-BIL-047

    NOT here, and NOT stubbed — a route that answers 501 is a promise:
      · POST /invoices/{id}/void — US-BIL-027, and its consequence message is
        server-computed (BR-BIL-009). A route without the reversal behind it
        would state a consequence it cannot honour. S30 says so by name.
      · There is no `POST /corrections/{id}/undo` and there never will be one.
        `bulk_corrections.explain_no_batch_rollback` is the sentence that goes
        where the button would have been, and this surface SERVES it on the case
        detail so the screen renders the reason rather than inventing one.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import (
    bulk_corrections,
    correction_reasons,
    corrections,
    delivery_seam,
    selectors,
    settings_seam,
    single_correction,
)
from apps.billing.correction_models import (
    CLASS_DOCUMENT,
    SCOPE_ACCOUNT,
    SCOPE_KINDS,
    SCOPE_SINGLE,
)
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from core import errors
from core.pagination import StandardPagination
from core.permissions import AdminOrClerk, AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

#: What this surface cannot answer, carried on the responses rather than left
#: for a caller to discover. Same discipline as `pending.PENDING_UNAVAILABLE`.
CORRECTIONS_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "reason_lookup_is_not_tenant_extensible_yet",
        "br_ref": "BR-BIL-014 · BR-BIL-041 · US-BIL-017",
        "detail": "correction reasons are REFERENCE DATA a tenant may extend (r10 #13) and "
        "that lookup table is not built. `apps/billing/correction_reasons.py` carries the "
        "seeded thirteen with their classes and REFUSES a code it cannot class rather than "
        "defaulting one — because defaulting would either raise a credit note for a "
        "spelling mistake or discharge a rate error with a reprint. So this vocabulary is "
        "read-only and a tenant cannot add to it yet.",
    },
    {
        "code": "void_is_not_a_correction_and_has_no_route",
        "br_ref": "BR-BIL-009 · US-BIL-027",
        "detail": "a bill that should never have existed is VOIDED, not corrected, and "
        "`POST /invoices/{id}/void` is US-BIL-027's and is not mounted. Its consequence "
        "message is computed server-side (BR-BIL-009), so a route without the reversal "
        "behind it would state a consequence it cannot honour. The Fix-a-bill screen names "
        "it as not offered here rather than drawing a control that cannot work.",
    },
    {
        "code": "approver_role_is_checked_but_the_gate_mode_is_not_settable",
        "br_ref": "BR-BIL-014 · OQ-072",
        "detail": "v1 requires a System Admin approval on EVERY correction and this "
        "surface enforces it with `SystemAdminOnly` on the approve route. "
        "`settings_seam.correction_approval_mode` exists for a tenant that wants a "
        "threshold instead, and no settings surface writes it — so the mode is read and "
        "REPORTED here, never used to widen the gate.",
    },
    {
        "code": "no_batch_rollback_ever",
        "br_ref": "BR-BIL-047 · CLAUDE.md rule 4",
        "detail": "there is no undo for an executed correction case, and there will not "
        "be one: the corrections that executed posted balanced journal entries and a "
        "posted entry cannot be un-posted, and their corrected bills are already queued "
        "for delivery. The remedy is a NEW case over exactly those bills. The sentence "
        "the screen renders is served on the case detail as `no_rollback`.",
    },
)


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="billing.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id from the session user,
    ROLE SERVER-ATTACHED by the identity layer (BE-04), never client input.

    The services behind this surface read `actor.role` (BR-BIL-027's publish
    right) and `actor.id` (`core.audit.money_action`, hard rule 7). Handing them
    the bare Django `User` gives them an object with no role, and a service that
    cannot resolve a role refuses — which is the right default and the wrong
    outcome for a request the permission layer has already authorised. The same
    shim `apps/tenancy/api.py` uses, for the same reason.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _date_field(payload: dict[str, Any], name: str) -> date:
    """A REQUIRED business date, from the caller. Never a server clock.

    BR-TEN-043 and gate G6: aging, posting periods and the back-bill window are
    all measured against the TENANT's today, and a correction previewed from
    another timezone must not silently judge a bill against a different day.
    """
    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.ops.date_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.date_format",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _optional_date(payload: dict[str, Any], name: str) -> date | None:
    if payload.get(name) in (None, ""):
        return None
    return _date_field(payload, name)


def _decimal_field(payload: dict[str, Any], name: str) -> Decimal | None:
    """A money argument as a STRING → Decimal. Never a float (CLAUDE.md rule 2).

    A JSON number is an IEEE double by the time it reaches here and 0.1 + 0.2 is
    not 0.3; a goodwill credit that arrived as a float would be wrong in the
    sixth place before any rule saw it. So a number is refused with the reason,
    not silently coerced.
    """
    raw = payload.get(name)
    if raw in (None, ""):
        return None
    if isinstance(raw, float):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.money_string",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.money_string",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _datetime_field(payload: dict[str, Any], name: str) -> datetime:
    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.ops.date_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.date_format",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _setting_or_absent(read: Any) -> tuple[Any, str | None]:
    """A tenant setting, or the REASON it cannot be read. Never a default.

    `settings_seam` refuses rather than falling back, and that is right for the
    write path: an unreadable back-bill cap is not twelve months, and defaulting
    it would let an upward correction past a cap the tenant's own settings set.

    On a READ, though, a refusal would 500 the vocabulary screen and a clerk
    would see nothing at all. So the catalog route reports the absence beside
    the value — an honest "we cannot read your tenant's back-bill window" beats
    both a crash and a plausible-looking 12 that nobody chose. **The write path
    does NOT use this**: `open_case` calls the seam directly and lets it refuse.
    """
    try:
        return read(), None
    except BillingConfigError as unreadable:
        return None, str(unreadable)


def _refusal(broken: BillingRuleError, default_br_ref: str) -> errors.BizError:
    """A service refusal, as the ONE catalog exception G9 allows.

    Same shape and same reasoning as `api._as_catalog_refusal`: every refusal
    that reaches here says *this cannot be done as asked, here is the rule and
    here is the sentence a clerk can act on*, and the sentence travels in
    `params.detail` because that is what BR-SHL-020 puts on screen. Picking
    among the nine BIZ codes per refusal would be this layer interpreting rules
    it does not own.
    """
    # `CR-180-BRC10` — the contract's refusals are BY `message_key` (a draft,
    # an open case, a reason not allowed for the scope, figures that moved…).
    # A service refusal that carries its own key keeps it, with its params;
    # every other one is the generic sentence, as before.
    key = getattr(broken, "message_key", None) or "billing.correction.refused"
    params = dict(getattr(broken, "params", None) or {})
    params.setdefault("detail", str(broken))
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(broken, "br_ref", None) or default_br_ref,
        message_key=key,
        params=params,
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def correction_reason_catalog(request: Any) -> Response:
    """US-BIL-017's reference data — every reason, its class, and what it DOES.

    The class travels as a WORD as well as a code (BR-BIL-041 / TC-1a: *"the
    class is shown in the operator's words … never as an enum value"*), so the
    screen can put "issues a corrected bill: the original is credited in full…"
    beside the reason a clerk is about to pick rather than the string
    `restatement`.

    `routed_elsewhere` is served too, and it is the half that stops work landing
    in the wrong workflow: an estimate replaced by an actual read, a bill that
    should never have existed, a period never billed, a payment on the wrong
    bill and a master-data-only fix are the five things people bring to a
    correction screen that are NOT corrections. EP-BIL-04 §1a asks the screen to
    *"say so by name rather than accepting the work"* — it cannot do that
    without the sentences.
    """
    require_tenant(request)
    approval_mode, approval_mode_absent = _setting_or_absent(
        settings_seam.correction_approval_mode
    )
    window_months, window_absent = _setting_or_absent(settings_seam.back_bill_cap_months)
    return Response(
        {
            "reasons": [
                {
                    "code": code,
                    "correction_class": klass,
                    "mechanism_in_words": correction_reasons.mechanism_in_words(klass),
                }
                for code, klass in sorted(correction_reasons.SEEDED_REASON_CLASSES.items())
            ],
            # ⚠ **NOT `sorted()`, AND THE ORDER IS THE RULE (`BR-BIL-042`,
            # `DEF-BIL-5350`).** `reasons` above and `routed_elsewhere` below
            # are both sorted, so this line reads like an oversight and is not
            # one: `CLASS_PRECEDENCE` is **R > C > D**, and the screen does not
            # re-implement that ranking — `fixABillContract.strongestClassFor`
            # takes the FIRST class served that is present among the ticked
            # reasons. Sorting these three serves `credit_only, document,
            # restatement`, and a case carrying a wrong read AND goodwill then
            # comes back **credit_only**: no corrected bill, a goodwill credit
            # instead, on a money path, with every type check and gate green.
            # `test_def_bil_5350__the_catalogue_serves_its_classes_strongest_first`
            # is what goes red; it was proved red on exactly that change.
            "classes": [
                {"code": klass, "mechanism_in_words": correction_reasons.mechanism_in_words(klass)}
                for klass in correction_reasons.CLASS_PRECEDENCE
            ],
            "routed_elsewhere": [
                {"code": code, "detail": detail}
                for code, detail in sorted(correction_reasons.ROUTED_ELSEWHERE.items())
            ],
            "scope_kinds": list(SCOPE_KINDS),
            "approver_role": single_correction.APPROVER_ROLE,
            # BOTH of these are the TENANT's settings and both are served as
            # `null` beside the reason when they cannot be read. A zero or a
            # hardcoded 12 here would be this surface inventing a finance figure
            # — and a screen that printed "12 months" over an unreadable setting
            # would tell a clerk a cap applies that nobody can vouch for.
            "approval_mode": approval_mode,
            "approval_mode_unavailable": approval_mode_absent,
            "backbill_window_months": window_months,
            "backbill_window_unavailable": window_absent,
            "unavailable": [dict(entry) for entry in CORRECTIONS_UNAVAILABLE],
        }
    )


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def correction_cases(request: Any) -> Response:
    """GET: the case list. POST: open a case — **which writes no money**.

    BR-BIL-014 is explicit that nothing money-bearing exists before approval,
    and `open_case` writes exactly three kinds of row: the case, its pinned
    bills and their impacts. The 201 this returns therefore means *"here is what
    it would cost"*, never *"it is done"* — which is why the response carries the
    preview and the standing statement rather than a success message.

    THE WRITE IS `AdminOrClerk` AND THE READ IS `AnyTenantRole`, checked in the
    body rather than at the decorator, because DRF gates a view and this route
    is two verbs. A4 gives Executive VIEW on Reads & Billing runs and
    BR-SHL-025 is server-enforced, so an Executive may look at a case and may
    not open one.
    """
    require_tenant(request)
    if request.method == "GET":
        paginator = StandardPagination()
        page = paginator.paginate_queryset(selectors.correction_case_queryset(), request)
        response = paginator.get_paginated_response(
            [selectors.correction_case_row(case) for case in (page or [])]
        )
        response.data["unavailable"] = [dict(entry) for entry in CORRECTIONS_UNAVAILABLE]
        return response

    if not AdminOrClerk().has_permission(request, None):
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-SHL-025")

    payload = _payload(request)
    # BR-BIL-041 / TC-10 — the silent-underbilling guard, fired on every open.
    # Translated at THIS boundary like every other service refusal: the guard
    # raises `BillingRuleError`, which is not a catalog exception, and an
    # untranslated one leaves the router with a 500 where the caller needs the
    # SENTENCE (*"answering a money reason with a document reissue is a silent
    # underbilling"*). A 500 tells an integrator their request was malformed
    # server-side; a 422 with that sentence tells them what to send instead.
    try:
        correction_reasons.refuse_supplied_mechanism(
            payload.get("mechanism") or payload.get("correction_class")
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-041") from refusal
    # ── `CR-180-BRC10` §3 · SEND — THE CASE IS OPENED HERE, WITH ITS ROWS ────
    # A body carrying `items` is the revamped wizard's Send: the scope, the
    # "What was wrong" rows and the `preview_hash` the clerk checked. It opens
    # the case only if the figures have not moved since. A body with
    # `reason_codes` is the older shape and takes the path below, unchanged
    # (CR-180 §Version and rollback: *"the old routes keep working"*).
    if "items" in payload:
        from apps.billing import correction_items, correction_jobs

        if correction_jobs.is_bulk(correction_jobs.scope_kind_of(payload.get("scope"))):
            # DEF-BIL-10091 — a BULK Send opens the case from the preview the
            # background job priced (`preview_job_id`); it prices nothing,
            # and it runs as a job too. The approval re-checks the figures.
            try:
                record, _row = correction_jobs.start_send(
                    payload.get("preview_job_id"),
                    preview_hash=str(payload.get("preview_hash") or ""),
                    actor=_actor(request),
                )
            except BillingRuleError as refusal:
                raise _refusal(refusal, "BR-BIL-044") from refusal
            return Response(_accepted(record, "send"), status=202)
        try:
            case = correction_items.open_at_send(
                payload.get("scope") or {},
                payload.get("items"),
                as_of=_date_field(payload, "as_of"),
                preview_hash=str(payload.get("preview_hash") or ""),
                actor=_actor(request),
            )
        except BillingRuleError as refusal:
            raise _refusal(refusal, "BR-BIL-014") from refusal
        except BillingConfigError as unreadable:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-BIL-021",
                message_key="billing.correction.refused",
                params={"detail": str(unreadable)},
            ) from unreadable
        return Response(_case_detail(case, request), status=201)
    reason_codes = payload.get("reason_codes")
    if not isinstance(reason_codes, list) or not reason_codes:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.correction.reasons_required",
            field_errors=[{"field": "reason_codes", "code": errors.VAL_REQUIRED}],
        )
    scope_kind = str(payload.get("scope_kind") or SCOPE_SINGLE)
    as_of = _date_field(payload, "as_of")
    posting_period = _optional_date(payload, "posting_period")
    goodwill = _decimal_field(payload, "goodwill_amount")
    balance_before = _decimal_field(payload, "balance_before")

    try:
        if scope_kind == SCOPE_SINGLE:
            invoice_ids = payload.get("invoice_ids") or (
                [payload["invoice_id"]] if payload.get("invoice_id") else []
            )
            if len(invoice_ids) != 1:
                raise errors.ValidationError(
                    errors.VAL_REQUIRED,
                    message_key="billing.correction.one_bill_required",
                    field_errors=[{"field": "invoice_id", "code": errors.VAL_REQUIRED}],
                )
            invoice = selectors.invoice_or_404(str(invoice_ids[0]))
            single = single_correction.open_for_bill(
                invoice,
                reason_codes=tuple(str(code) for code in reason_codes),
                actor=_actor(request),
                as_of=as_of,
                posting_period=posting_period,
                goodwill_amount=goodwill,
                balance_before=balance_before,
                backbill_window_months=settings_seam.back_bill_cap_months(),
                theft_exempt=bool(payload.get("theft_exempt")),
            )
            case = single.case
        else:
            invoices = bulk_corrections.resolve_scope(
                kind=scope_kind,
                bill_run_id=payload.get("bill_run_id"),
                cycle_id=payload.get("cycle_id"),
                plan_id=payload.get("plan_id"),
                service_code=payload.get("service_code"),
                period_start=_optional_date(payload, "period_start"),
                period_end=_optional_date(payload, "period_end"),
                invoice_ids=tuple(payload.get("invoice_ids") or ()),
            )
            case = bulk_corrections.open_case(
                reason_codes=tuple(str(code) for code in reason_codes),
                scope_kind=scope_kind,
                scope={
                    key: value
                    for key, value in payload.items()
                    if key
                    in (
                        "bill_run_id",
                        "cycle_id",
                        "plan_id",
                        "service_code",
                        "period_start",
                        "period_end",
                    )
                    and value not in (None, "")
                }
                # A class-D bulk case carries the corrected document facts on the
                # scope, because that is where `_execute_one` reads them from.
                | (
                    {"corrected_payload": dict(payload["corrected_payload"])}
                    if isinstance(payload.get("corrected_payload"), dict)
                    else {}
                ),
                invoices=invoices,
                actor=_actor(request),
                posting_period=posting_period,
                goodwill_amount=goodwill,
                as_of=as_of,
                backbill_window_months=settings_seam.back_bill_cap_months(),
                theft_exempt=bool(payload.get("theft_exempt")),
            )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal
    except BillingConfigError as unreadable:
        # The back-bill cap is a TENANT setting and the seam refuses rather than
        # defaulting it (BR-BIL-021). Refusing here is the same decision one
        # layer up: opening a case against an unreadable cap would let an upward
        # correction past a window the tenant's own settings set. It is a 422
        # with the reason, never a 500 — the clerk can act on "your billing
        # settings have not been published yet".
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-021",
            message_key="billing.correction.refused",
            params={"detail": str(unreadable)},
        ) from unreadable
    return Response(_case_detail(case, request), status=201)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def correction_scope_resolve(request: Any) -> Response:
    """`GET /corrections/resolve` — the bills a scope resolves to, PAGED, with totals.

    `CR-101-BRC03` §06, screen 26 (p133): step 1 shows *"the bills it resolves
    to, with what each asked and what has been paid"* BEFORE a reason is
    picked and before any case exists — `BILL · PERIOD · AMOUNT · PAID ·
    STATE` and a totals row over the whole scope. This is that read. It writes
    nothing (not even a case row), takes the same selector vocabulary as the
    POST (`scope_kind` + `bill_run_id` / `cycle_id` / `plan_id` /
    `service_code` / `period_start` + `period_end` / `invoice_id(s)`), and
    resolves through the ONE filter `open_case` will pin from, so what the
    clerk saw in step 1 is what the case holds in step 2.

    Paginated by the standard envelope (`page` / `per`, `NFR-3`): a run at T5
    is 40,000 bills, the page is fifty, and `totals` is computed in SQL over
    all of them rather than summed from the page. `AnyTenantRole`: it is a
    read, and an Executive may look (BR-SHL-025's split, as `correction_cases`
    states it).
    """
    require_tenant(request)
    params = request.query_params
    scope_kind = str(params.get("scope_kind") or SCOPE_SINGLE)
    invoice_ids = [one for one in params.getlist("invoice_ids") if one]
    if not invoice_ids and params.get("invoice_id"):
        invoice_ids = [params["invoice_id"]]
    # `CR-180-BRC10` §1 — `account` (one customer: `account_id` + the bills)
    # and `price_mistake` (`period_start`/`period_end` + `wrong_kind` +
    # `wrong_id`) join the vocabulary; bills an open case holds are not
    # offered and are LISTED in `excluded` with the drafts the clerk named.
    selectors_ = {
        "bill_run_id": params.get("bill_run_id") or None,
        "cycle_id": params.get("cycle_id") or None,
        "plan_id": params.get("plan_id") or None,
        "service_code": params.get("service_code") or None,
        "period_start": _optional_date(params, "period_start"),
        "period_end": _optional_date(params, "period_end"),
        "wrong_kind": params.get("wrong_kind") or None,
        "wrong_id": params.get("wrong_id") or None,
    }
    try:
        queryset = bulk_corrections.resolve_scope_queryset(
            kind=scope_kind,
            invoice_ids=tuple(invoice_ids),
            account_id=params.get("account_id") or None,
            exclude_in_flight=True,
            **selectors_,
        )
        excluded = bulk_corrections.excluded_from_scope(
            kind=scope_kind,
            account_id=params.get("account_id") or None,
            invoice_ids=tuple(invoice_ids),
            **selectors_,
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    table = bulk_corrections.scope_table(
        tuple(page or ()), queryset=queryset, scope_kind=scope_kind
    )
    response = paginator.get_paginated_response(table["rows"])
    response.data["totals"] = table["totals"]
    response.data["correctable_statuses"] = table["correctable_statuses"]
    response.data["narrowed_by"] = table["narrowed_by"]
    response.data["problems"] = table["problems"]
    response.data["scope_kind"] = scope_kind
    response.data["excluded"] = excluded
    return response


def _positive_int(raw: Any) -> int | None:
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def correction_options(request: Any) -> Response:
    """`GET /corrections/options` — contract A2. **Writes nothing.**

    What the "What was wrong" row selects offer: the plans and their versions,
    the rate schedules and theirs, the taxes, the charge codes (base charges
    excluded — they come with the plan version, decision log item 7), the
    discount programmes and the price-mistake targets. With a scope (the same
    params as `/resolve`), also the meters the bills were priced from, the
    bills' charge lines and what the first bill was billed on — the defaults
    a row shows before the clerk changes them (decision log item 6).
    """
    require_tenant(request)
    params = request.query_params
    from apps.billing import correction_answer

    scope: dict[str, Any] | None = None
    if params.get("scope_kind"):
        scope = {
            "kind": params.get("scope_kind"),
            **{
                key: params.get(key)
                for key in (
                    "account_id",
                    "bill_run_id",
                    "cycle_id",
                    "plan_id",
                    "service_code",
                    "period_start",
                    "period_end",
                    "wrong_kind",
                    "wrong_id",
                )
                if params.get(key)
            },
        }
        ids = [one for one in params.getlist("invoice_ids") if one]
        if ids:
            scope["invoice_ids"] = ids
    try:
        return Response(correction_answer.options(scope))
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def correction_preview(request: Any) -> Response:
    """`POST /corrections/preview` — `CR-180-BRC10` §2. **WRITES NOTHING.**

    The scope and the "What was wrong" rows in; the corrected bills out: the
    class derived across the rows (R > C > D), per bill the nine sections, the
    old and new bill laid out by service and rate type, the posting month and
    the new due date; for bulk the aggregate with up and down apart; the page
    changes; the bills not offered; and the `preview_hash` Send must quote.

    No case, no row, no saved reading — BR-BIL-014, and the decision log's own
    measurement of the old flow, where step 1's Continue opened a case that then
    blocked the bill. A read: `AnyTenantRole` may look, as `/resolve` allows.
    """
    require_tenant(request)
    payload = _payload(request)
    from apps.billing import correction_items, correction_jobs

    scope = payload.get("scope") or {}
    if correction_jobs.is_bulk(correction_jobs.scope_kind_of(scope)):
        # DEF-BIL-10091 — a BULK preview prices every bill of a run, which is
        # minutes, so it is a background job: 202 + the job id, the screen
        # polls `/jobs/{id}` for "Working out 38 bills · 12 done" and reads
        # the answer, a page at a time, from `GET /corrections/jobs/{id}`.
        try:
            correction_reasons.refuse_supplied_mechanism(
                payload.get("mechanism") or payload.get("correction_class")
            )
            record, _row = correction_jobs.start_preview(
                scope,
                payload.get("items"),
                as_of=_date_field(payload, "as_of"),
                actor=_actor(request),
            )
        except BillingRuleError as refusal:
            raise _refusal(refusal, "BR-BIL-014") from refusal
        return Response(_accepted(record, "preview"), status=202)
    try:
        correction_reasons.refuse_supplied_mechanism(
            payload.get("mechanism") or payload.get("correction_class")
        )
        body = correction_items.preview(
            payload.get("scope") or {},
            payload.get("items"),
            as_of=_date_field(payload, "as_of"),
            actor=_actor(request),
            # A3 — a bulk preview's per-bill rows, paged; totals cover all.
            page=_positive_int(payload.get("page")),
            per=_positive_int(payload.get("per")),
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal
    except BillingConfigError as unreadable:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-021",
            message_key="billing.correction.refused",
            params={"detail": str(unreadable)},
        ) from unreadable
    return Response(body)


def _accepted(record: dict[str, Any], act: str) -> dict[str, Any]:
    """The 202 body (B12 r1): where to poll, and which act it is."""
    from core import jobs as core_jobs

    return {**core_jobs.accepted(record), "act": act}


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def correction_job(request: Any, job_id: str) -> Response:
    """`GET /corrections/jobs/{job_id}` — a bulk act's state and answer
    (`DEF-BIL-10091`). Reads only.

    `status` / `progress` are the job record's (the same `/jobs/{id}` serves);
    `refusal` is the act's refusal by `message_key`; `preview` is a stored
    preview, ONE PAGE of its bills (`page`, `per` — NFR-3), its totals over
    all of them; `case` is the case a Send opened or an approval issued, with
    `result` once the bills have run."""
    require_tenant(request)
    from apps.billing import correction_jobs

    row = correction_jobs.job_row(job_id)
    if row is None:
        raise errors.NotFoundError()
    page = _positive_int(request.query_params.get("page")) or 1
    per = _positive_int(request.query_params.get("per")) or correction_jobs.DEFAULT_PER
    body: dict[str, Any] = {
        "job_id": str(row.job_id),
        "act": row.act,
        **correction_jobs.job_state(row),
        "refusal": row.refusal,
        "preview": None,
        "case": None,
    }
    if row.act == "preview":
        body["preview"] = correction_jobs.preview_page(row, page=page, per=per)
    if row.case_id is not None:
        case = selectors.correction_case_or_404(str(row.case_id))
        detail = _case_detail(case, request)
        if row.result is not None:
            detail["result"] = row.result
        body["case"] = detail
    return Response(body)


def _case_detail(case: Any, request: Any = None) -> dict[str, Any]:
    """One case, as the approver reads it. Reads only; decides nothing.

    A SINGLE case carries BR-BIL-044's nine sections — *"all required, none
    collapsible away"*, and four of them read **none** on a class-D case, which
    is the epic's own reason the two mechanisms are impossible to confuse on
    screen. A BULK case carries the aggregate panel instead, because *"one
    signature cannot honestly cover both shapes"*: an approver of four hundred
    bills reads ↑/↓ counts and totals, not nine sections about one customer.
    """
    rows = bulk_corrections.case_bills(case)
    detail: dict[str, Any] = {
        **selectors.correction_case_row(case),
        "bills_detail": [selectors.correction_bill_row(row) for row in rows],
        # p137's fifth row — the bills the back-bill cap took out of this case
        # (PO 2026-09-15: *"in such sitution 6 bills only ; 7th is not valid
        # case"*). Served off the STORED preview, like every other figure on
        # this screen, so an approver reads what was previewed rather than a
        # fresh judgment made after they pressed approve (BR-BIL-044).
        # Empty on every case opened before 2026-09-15 and on every case where
        # nothing was capped — the two are the same thing to a reader here,
        # which is honest: neither case had a bill removed.
        "excluded": list((case.preview or {}).get("excluded") or []),
        "no_rollback": bulk_corrections.explain_no_batch_rollback(),
        "unavailable": [dict(entry) for entry in CORRECTIONS_UNAVAILABLE],
    }
    # `CR-180-BRC10` — the case's rows (B3), as the approver reads them.
    detail["items"] = list((case.preview or {}).get("items") or [])
    # A4 — the A3 answer the clerk SENT (stored at Send, never recomputed —
    # BR-BIL-044), who signs and who sent it, and whether THIS viewer may
    # approve: decided here, because the gate is the server's (US-BIL-017
    # TC-4) — a System Admin, on a case that is waiting.
    from apps.billing import correction_answer
    from apps.billing.correction_models import CASE_PENDING_APPROVAL, CASE_PREVIEW

    detail["preview"] = (case.preview or {}).get("answer")
    detail["approval"] = correction_answer.approval(case)
    detail["viewer_can_approve"] = bool(
        request is not None
        and getattr(request, "tenant_role", None) == "system_admin"
        and case.status in (CASE_PREVIEW, CASE_PENDING_APPROVAL)
    )
    # DEF-BIL-10535 — the approval step's *Email · Paper · Both*.
    detail["delivery"] = _delivery_offer(case, rows)
    if case.scope_kind in (SCOPE_SINGLE, SCOPE_ACCOUNT) and len(rows) == 1:
        from apps.billing import models

        invoice = models.Invoice.objects.get(tenant_id=case.tenant_id, pk=rows[0].invoice_id)
        single = single_correction.SingleCase(case=case, bill_row=rows[0], invoice=invoice)
        detail["sections"] = single_correction.nine_sections(single)
        detail["section_order"] = [name for _, name in single_correction.PREVIEW_SECTIONS]
        detail["chain"] = single_correction.chain_of(invoice)
    else:
        detail["aggregate"] = bulk_corrections.aggregate(case).as_dict()
        if case.scope_kind == SCOPE_ACCOUNT:
            # One customer, several months: BR-BIL-044's nine sections PER
            # BILL (contract §2), keyed by the bill — the approver reads each.
            from apps.billing import models

            invoices = {
                str(one.pk): one
                for one in models.Invoice.objects.filter(
                    tenant_id=case.tenant_id, pk__in=[row.invoice_id for row in rows]
                )
            }
            detail["bill_sections"] = {
                str(row.invoice_id): single_correction.nine_sections(
                    single_correction.SingleCase(
                        case=case, bill_row=row, invoice=invoices[str(row.invoice_id)]
                    )
                )
                for row in rows
            }
    return detail


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def correction_case_item(request: Any, case_id: str) -> Response:
    """The case an approver is about to sign, or the record of one that ran."""
    require_tenant(request)
    case = selectors.correction_case_or_404(case_id)
    try:
        return Response(_case_detail(case, request))
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-044") from refusal


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-BIL-014 v1 / OQ-072 — every case
def correction_case_approve(request: Any, case_id: str) -> Response:
    """The gate. **Server-side, and that is the whole point** (US-BIL-017 TC-4).

    `SystemAdminOnly` is not a convenience over a disabled button: the preview
    is an artifact, not a permission, and a client that POSTs straight to
    `/execute` without this must be refused by the SERVER. BR-BIL-014 v1
    (OQ-072 closed) puts every correction behind a System Admin.

    `preview_hash` is what the approver's screen was rendered from and is
    REQUIRED here rather than optional. `bulk_corrections.approve` treats a null
    as "no claim" and lets it through, which is right for a service used by a
    resumed job — but a browser always knows which figures it drew, and an
    approval that did not say which artifact it covered would be exactly the
    signature BR-BIL-044 exists to prevent.
    """
    require_tenant(request)
    case = selectors.correction_case_or_404(case_id)
    payload = _payload(request)
    preview_hash = payload.get("preview_hash")
    if not isinstance(preview_hash, str) or not preview_hash:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.correction.preview_hash_required",
            field_errors=[{"field": "preview_hash", "code": errors.VAL_REQUIRED}],
        )
    try:
        approved = bulk_corrections.approve(
            case,
            approver=_actor(request),
            on_date=_date_field(payload, "approved_on"),
            preview_hash=preview_hash,
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal
    return Response(_case_detail(approved, request))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def correction_case_execute(request: Any, case_id: str) -> Response:
    """Run the approved case. Idempotent, resumable, no rollback (rule 6).

    A repeat is not an error and does not answer 409: `bulk_corrections.execute`
    skips a row already `done` and REPORTS it as skipped, so a double-clicked
    button, a retry storm and a resumed worker all leave exactly one credit note
    and one rebill per bill. The response carries the skipped list by name, so
    the screen can say *"3 already done"* instead of showing a silent success
    over work it did not do.

    THE REBILL'S TEMPLATE PIN IS RESOLVED HERE, not defaulted from the original.
    BR-BIL-026 pins the CURRENT published version at rebill issue, and
    `templates_service.resolve_for` is the one implementation of that resolution
    order. Silently reprinting on the superseded version the original carried is
    the unsafe option, so it is the one nobody can take (hard-won law 3).
    """
    require_tenant(request)
    case = selectors.correction_case_or_404(case_id)
    payload = _payload(request)
    template_id = None
    template_version = None
    if case.correction_class != CLASS_DOCUMENT:
        from apps.billing import templates_service

        try:
            template, version = templates_service.resolve_for(
                consumer_category=payload.get("consumer_category"),
            )
        except BillingRuleError as refusal:
            raise _refusal(refusal, "BR-BIL-026") from refusal
        template_id, template_version = template.pk, version.version_no
    from apps.billing import correction_jobs

    if correction_jobs.is_bulk(case.scope_kind) and (case.scope or {}).get(
        bulk_corrections.ITEMS_SCOPE_MARKER
    ):
        # DEF-BIL-10091 — Try again on a bulk case runs the bills not yet
        # done, in the background like the approval that started it.
        try:
            record, _row = correction_jobs.start_issue(
                case,
                preview_hash=None,
                on_date=_date_field(payload, "on_date"),
                issued_at=_datetime_field(payload, "issued_at"),
                template_id=template_id,
                template_version=template_version,
                actor=_actor(request),
                resume=True,
            )
        except BillingRuleError as refusal:
            raise _refusal(refusal, "BR-BIL-014") from refusal
        return Response(_accepted(record, "approve_issue"), status=202)
    try:
        result = bulk_corrections.execute(
            case,
            issued_at=_datetime_field(payload, "issued_at"),
            on_date=_date_field(payload, "on_date"),
            template_id=template_id,
            template_version=template_version,
            actor=_actor(request),
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal
    case.refresh_from_db()
    return Response(
        {
            **_case_detail(case, request),
            "result": {
                "case_id": result.case_id,
                "status": result.status,
                "succeeded": list(result.succeeded),
                # A per-bill failure is a REASON, never a count: BR-BIL-047 makes
                # abandoning one an explicit reasoned act, and nobody can reason
                # about "2 failed".
                "failed": [
                    {"invoice_id": invoice_id, "reason": reason}
                    for invoice_id, reason in result.failed
                ],
                "skipped_already_done": list(result.skipped_already_done),
                "summary": result.summary(),
            },
        }
    )


def _rebill_template(payload: dict[str, Any], case: Any) -> tuple[Any, int | None]:
    """The rebill's template pin (BR-BIL-026), resolved — the same resolution
    `/execute` makes. None for a case that issues no new bill."""
    if case.correction_class == CLASS_DOCUMENT:
        return None, None
    from apps.billing import templates_service

    try:
        template, version = templates_service.resolve_for(
            consumer_category=payload.get("consumer_category"),
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-026") from refusal
    return template.pk, version.version_no


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-BIL-014 v1 / OQ-072 — the approver
def correction_case_approve_and_issue(request: Any, case_id: str) -> Response:
    """`POST /corrections/{id}/approve-and-issue` — `CR-180-BRC10` §4 (B10).

    The approver opens Send and presses *Approve and issue* (decision log
    2026-10-12, step 4): the gate and the job as ONE act, server-side. The
    approval binds `preview_hash` (a mismatch refuses, `figuresMoved`), then
    every bill runs on its own — credit note + new bill, two balanced entries,
    payments' re-allocation, delivery rows, audit — and a bill that fails
    leaves nothing and does not undo the others (BR-BIL-047). The answer is
    `/execute`'s: per bill `succeeded` / `failed` / `skipped_already_done`.

    `on_date` and `issued_at` are the caller's (BR-TEN-043 — never a clock on
    a money path), exactly as `/approve` and `/execute` take them.
    """
    require_tenant(request)
    case = selectors.correction_case_or_404(case_id)
    payload = _payload(request)
    preview_hash = payload.get("preview_hash")
    if not isinstance(preview_hash, str) or not preview_hash:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.correction.preview_hash_required",
            field_errors=[{"field": "preview_hash", "code": errors.VAL_REQUIRED}],
        )
    on_date = _date_field(payload, "on_date")
    issued_at = _datetime_field(payload, "issued_at")
    template_id, template_version = _rebill_template(payload, case)
    from apps.billing import correction_items, correction_jobs

    if correction_jobs.is_bulk(case.scope_kind):
        if payload.get("delivery") is not None:
            # DEF-BIL-10535 — the choice is Fix-a-bill's for ONE customer
            # (decision log 2026-10-22, point 4). Refused by name rather than
            # ignored: a silently dropped field is worse than a refusal.
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="billing.correction.delivery_bulk",
                field_errors=[{"field": "delivery", "code": errors.VAL_FORMAT}],
            )
        # DEF-BIL-10091 — check every bill, approve, issue: a background job.
        try:
            record, _row = correction_jobs.start_issue(
                case,
                preview_hash=preview_hash,
                on_date=on_date,
                issued_at=issued_at,
                template_id=template_id,
                template_version=template_version,
                actor=_actor(request),
            )
        except BillingRuleError as refusal:
            raise _refusal(refusal, "BR-BIL-044") from refusal
        return Response(_accepted(record, "approve_issue"), status=202)
    delivery = _clerk_delivery(case, payload)
    try:
        with (
            delivery_seam.clerk_delivery_choice(delivery)
            if delivery is not None
            else nullcontext()
        ):
            # DEF-BIL-10535 — the rebill's `issue_invoice` (reached through
            # `corrections.execute_restatement`) asks `elected_channels`, which
            # answers the clerk's choice for the length of this block.
            result = correction_items.approve_and_issue(
                case,
                approver=_actor(request),
                preview_hash=preview_hash,
                on_date=on_date,
                issued_at=issued_at,
                template_id=template_id,
                template_version=template_version,
            )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-014") from refusal
    case.refresh_from_db()
    return Response(
        {
            **_case_detail(case, request),
            "result": {
                "case_id": result.case_id,
                "status": result.status,
                "succeeded": list(result.succeeded),
                "failed": [
                    {"invoice_id": invoice_id, "reason": reason}
                    for invoice_id, reason in result.failed
                ],
                "skipped_already_done": list(result.skipped_already_done),
                "summary": result.summary(),
                # DEF-BIL-10535 — the channels the new bill was queued on, as
                # the clerk chose them (or the original's, when no choice came).
                "delivery": delivery,
            },
        }
    )


def _delivery_offer(case: Any, rows: Any) -> dict[str, Any] | None:
    """Fix-a-bill's *Email · Paper · Both* for ONE customer's case, or None.

    `DEF-BIL-10535`, PO 2026-10-22 Q1, verbatim: *"C. The clerk chooses Email,
    Paper or Both on the approval step, with the original bill's channels
    ticked to start."* `preselected` is the original bill's channels
    (`delivery_seam.original_delivery_choice`); `email_on_file` greys *Email*
    and *Both* on screen and the server refuses them by name. A bulk case, or a
    case already past approval, is offered nothing (decision log 2026-10-22,
    point 4).

    Worked, Daniel Thomas (AC-2026-00071): original queued by post only, email
    on file → `{"preselected": "paper", "email_on_file": true}`; the clerk may
    pick *Both*.
    """
    from apps.billing import correction_jobs
    from apps.billing.correction_models import CASE_PENDING_APPROVAL, CASE_PREVIEW

    if correction_jobs.is_bulk(case.scope_kind) or case.status not in (
        CASE_PREVIEW,
        CASE_PENDING_APPROVAL,
    ):
        return None
    rows = list(rows)
    accounts = {row.account_id for row in rows if row.account_id is not None}
    on_file = bool(accounts) and all(
        delivery_seam.email_on_file(account) is True for account in accounts
    )
    preselected = delivery_seam.original_delivery_choice([row.invoice_id for row in rows])
    if preselected in delivery_seam.DELIVERY_CHOICES_WITH_EMAIL and not on_file:
        # The original went by email to an address that is no longer on file:
        # start from what can still be sent rather than a greyed choice.
        preselected = "paper"
    return {
        "choices": list(delivery_seam.CORRECTION_DELIVERY_CHOICES),
        "preselected": preselected,
        "email_on_file": on_file,
    }


def _clerk_delivery(case: Any, payload: dict[str, Any]) -> str | None:
    """The channels for this approval: the clerk's answer, else the original's.

    `None` only where neither is knowable (the queue cannot be asked), and the
    rebill then takes the account's own channels as every bill does. Email or
    Both with no email on file is refused by name before anything moves.
    """
    offer = _delivery_offer(case, bulk_corrections.case_bills(case))
    asked = payload.get("delivery")
    if asked is None:
        return offer["preselected"] if offer is not None else None
    if asked not in delivery_seam.CORRECTION_DELIVERY_CHOICES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="billing.correction.delivery_unknown",
            field_errors=[{"field": "delivery", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    if asked in delivery_seam.DELIVERY_CHOICES_WITH_EMAIL and not (
        offer is not None and offer["email_on_file"]
    ):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.correction.delivery_no_email",
            field_errors=[{"field": "delivery", "code": errors.VAL_FORMAT}],
        )
    return str(asked)


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def correction_case_abandon(request: Any, case_id: str) -> Response:
    """Close a case over unresolved failures — with a reason (BR-BIL-047).

    A blank reason is refused by the service and the refusal is the point:
    those bills are still wrong, and the record has to say why nobody is going
    to fix them. "Closed" with no explanation is indistinguishable from
    "finished".
    """
    require_tenant(request)
    case = selectors.correction_case_or_404(case_id)
    payload = _payload(request)
    try:
        closed = bulk_corrections.abandon(
            case,
            reason=str(payload.get("reason") or ""),
            actor=_actor(request),
            on_date=_date_field(payload, "on_date"),
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-047") from refusal
    return Response(_case_detail(closed, request))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def invoice_chain(request: Any, invoice_id: str) -> Response:
    """US-BIL-015 TC-3 — *"the chain original ↔ credit note ↔ rebill, navigable
    both ways"*, served for S30's bill detail.

    BOTH DIRECTIONS COME OFF ONE COLUMN (`invoices.corrects_invoice_id`, PO
    2026-08-12 closing OQ-120), which is why the chain cannot fork or disagree
    with itself. `is_latest` is what BR-BIL-048 lets a new case be opened on —
    so a screen can disable "Fix this bill" on a superseded original AND name
    its replacement, instead of letting a clerk find out at preview time.
    """
    require_tenant(request)
    invoice = selectors.invoice_or_404(invoice_id)
    try:
        return Response(single_correction.chain_of(invoice))
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-048") from refusal


urlpatterns = [
    # ORDER IS LOAD-BEARING: `corrections/reasons` is all-static and MUST be
    # declared above `corrections/<str:case_id>`, or the word "reasons" resolves
    # as a case id and the vocabulary 404s on a case that never existed. This is
    # exactly the `deposits/import` shape the payments lane recorded.
    path("corrections/reasons", correction_reason_catalog),
    # CR-101-BRC03 §06 — step 1's scope table. Registered BEFORE the
    # `<str:case_id>` route so `resolve` is never read as a case id.
    path("corrections/resolve", correction_scope_resolve),
    # CR-180-BRC10 §2 — the preview that writes nothing. Static, so BEFORE
    # `<str:case_id>` for the same reason as the two above.
    path("corrections/preview", correction_preview),
    # CR-180-BRC10 A2 — what the row selects offer. Static, so above the id.
    path("corrections/options", correction_options),
    # DEF-BIL-10091 — a bulk act's state and answer. Static prefix, so above
    # the id route.
    path("corrections/jobs/<str:job_id>", correction_job),
    path("corrections", correction_cases),
    path("corrections/<str:case_id>", correction_case_item),
    path("corrections/<str:case_id>/approve", correction_case_approve),
    path("corrections/<str:case_id>/approve-and-issue", correction_case_approve_and_issue),
    path("corrections/<str:case_id>/execute", correction_case_execute),
    path("corrections/<str:case_id>/abandon", correction_case_abandon),
    path("invoices/<str:invoice_id>/chain", invoice_chain),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-015@a71c4e2 (sha1[:7] of the three sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-04-corrections.md — US-BIL-015 + US-BIL-016 + US-BIL-017 + US-BIL-031 — · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-014/041..048 · 04-docs/01-spec/11b-api-audit.md §2.8 correction rows; so a later change to any of them makes this stamp findable as stale in one grep. Co-packets US-BIL-016, US-BIL-017, US-BIL-031, same three sources)
# generated: 2026-08-16 by story-coder (billing SURFACE lane — the endpoints five correction modules each recorded as "unbuilt" in their own trailers)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_bil_surface_apis.py could not resolve `/corrections` through the root URLconf before this file was included, and the approval-gate test was shown to fail against `AnyTenantRole` before `SystemAdminOnly` went on. Both failures are quoted verbatim in the lane report. pytest✔ · run_gates✔ · golden 33/33✔
# exceptions: E3 THE PROTOTYPE'S "Change an amount — Edit specific line items on the bill" (line 3502) IS NOT PORTED and cannot be: `invoices`/`invoice_lines` are append-only under hard rule 4 and the database refuses the UPDATE, so the control would offer something the storage layer will not do. Reported as a prototype divergence · E3 the prototype's "Cancel this bill" is a VOID (US-BIL-027) with no endpoint in this build — named on screen as not-offered rather than drawn as a dead control · E3 `preview_hash` is REQUIRED on approve although the service accepts a null: a browser always knows which figures it drew, and an approval that did not name its artifact is the signature BR-BIL-044 exists to prevent · E3 the approve route is `SystemAdminOnly` at the DECORATOR (BR-BIL-014 v1 / OQ-072) — the gate is the server's, not a disabled button's · E3 GET is `AnyTenantRole` and the POST on the same path re-checks `AdminOrClerk` in the body, because DRF gates a view and that route is two verbs · E3 a money argument arriving as a JSON float is REFUSED rather than coerced (rule 2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
