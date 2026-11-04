# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C2 / task T7 — unbilled revenue accrual at close.
#           Screens: S42 (the close checklist this completes)
#           NOTE: no US-ID ON PURPOSE — G10 reads a Trace-header US-ID as "this
#           file ships that story's TCs" and no story owns C2 yet.
# Rules:    BR-LED-791 (how unbilled revenue is measured and priced) ·
#           BR-LED-006 (the close checklist and its role gate) · BR-LED-005
#           (the day-1 auto-reversal) · BR-TEN-043 (posted_at is an INPUT) ·
#           BR-TEN-038 (a closed period is never posted into) · BR-LED-015
#           (every finance action audits) · CLAUDE.md rule 1 · rule 2 · rule 7
# Tests:    06-backend/tests/test_cr060_t7_unbilled_accrual.py
# Impacts:  apps/ledger/unbilled_accrual.py (the service this exposes) ·
#           config/urls.py (one include, beside finance_api and journal_api)
# ───────────────────────────────────────────────────────
"""The month-end postings: preview each figure, then post it.

    GET  /finance/accruals/unbilled        the figure, and the reads it came from
    POST /finance/accruals/unbilled/post   post it — DR 1210 / CR the services
    GET  /finance/accruals/unpaid-costs    the figure, and the invoices behind it
    POST /finance/accruals/unpaid-costs/post   DR the cost accounts / CR accrued
    GET  /finance/depreciation             the period's charge and its assets
    POST /finance/depreciation/post        DR depreciation / CR accumulated

⚠ **THIS FILE WAS C2's ALONE UNTIL 2026-09-02** and its docstring said so. C17
(task T7b) and C20 (task T7f) landed the same day and are here rather than in
files of their own for the reason the next paragraph gives about `finance_api`:
these three are ONE surface — the things a clerk does at a period end — and a
module per posting would put three copies of `_window`, `_moment` and `_refused`
in three places, which is how two of them come to validate a date differently.

════════════════════════════════════════════════════════════════════════════
WHY A FILE OF ITS OWN RATHER THAN TWO MORE ROUTES IN `finance_api.py`
════════════════════════════════════════════════════════════════════════════
The same reason `journal_api.py` and `cost_api.py` are their own files and
`config/urls.py` includes each at `""`: Django resolves by whole URL, not by
prefix, so a module per surface costs nothing at routing time and keeps one
lane's edit out of another lane's file. It also keeps `finance_api.py`'s own
guarantee intact — that file's routes are the close, the export and the
remittance, and its docstring is about those.

════════════════════════════════════════════════════════════════════════════
THE PREVIEW WRITES NOTHING, AND IT IS THE SAME COMPUTATION THE POST USES
════════════════════════════════════════════════════════════════════════════
C2 asks for a preview *"before posting — the figure, and the reads it came
from"*. `preview_unbilled_revenue` is the function `accrue_unbilled_revenue`
itself calls, so the number a clerk confirms is the number that posts. A second
implementation for the preview is exactly how a confirm screen comes to show a
figure the books never receive.

**A `null` total is not a zero.** `total: null` means a read this accrual
depends on is not published, and the screen must say so rather than draw 0.00 —
a zero unbilled accrual is the claim *"nothing is unbilled"*, made over books
that may hold a month of it. Every absence rides in `unavailable` and `excluded`
with a name and a COUNT.

⚠ **ONE NEW MESSAGE KEY IS OWED AND IS REPORTED, NOT LANDED.** The refusal
renders under `ledger.accrual.refused`, and the eleven locale catalogues are
another lane's files. The key and its English text are in this lane's report;
until the locale lane lands it the response still carries the service's own
sentence in `params.detail`, which is what a terminal and the audit trail read.
Every other key on this surface already exists (`ledger.report.date_invalid`,
`ledger.report.period_required`, `ledger.report.range_inverted`,
`ledger.je.posted_at_required`, `ledger.payload_not_object`), which is why there
is exactly one.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ledger import allowance
from apps.ledger import depreciation, manual_je, models, unbilled_accrual, unpaid_cost_accrual, wire
from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="ledger.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """WHO asked for the accrual, from the SESSION — never from the body (rule 7)."""
    return getattr(request, "user", None)


def _date_value(raw: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="ledger.report.date_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


def _window(source: Any, *, getter: str = "get") -> tuple[date, date]:
    """`from` + `to`, both REQUIRED — the period being accrued.

    An open bound is refused for `finance_api._window`'s reason: an accrual is
    *for a period*, and a window that meant something different to every caller
    would put a different figure in the books each time.
    """
    read = getattr(source, getter)
    raw_start, raw_end = read("from"), read("to")
    for field, raw in (("from", raw_start), ("to", raw_end)):
        if raw is None or str(raw).strip() == "":
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="ledger.report.period_required",
                field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
            )
    start = _date_value(raw_start, "from")
    end = _date_value(raw_end, "to")
    if start > end:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="ledger.report.range_inverted",
            params={"from": start.isoformat(), "to": end.isoformat()},
            field_errors=[{"field": "from", "code": errors.VAL_RANGE}],
        )
    return start, end


def _moment(payload: dict[str, Any], name: str = "posted_at") -> datetime:
    """The instant the accrual entered the books — an INPUT (BR-TEN-043, G6).

    A double-submitted *Post accrual* must stamp ONE moment. The replay guard
    already makes the second press a no-op; the input is what makes the FIRST
    press reproducible when a close is re-run over a day the host was down.
    """
    raw = payload.get(name)
    if raw is None or str(raw).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.je.posted_at_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    text = str(raw).strip()
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.combine(date.fromisoformat(text), datetime.min.time())
        except (TypeError, ValueError) as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="ledger.report.date_invalid",
                field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
            ) from problem
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_timezone.utc)
    return moment


def _posting_shape(*, reverses: bool, period_end: date) -> dict[str, Any]:
    """**THE TWO FACTS THAT STOP THE $40,000 ERROR, SERVED RATHER THAN INFERRED.**

    The Finance blueprint's screen 1·4 (p026) draws a `Type` and a `Reverses`
    column because *"the difference has to be seen, not read"*: two of these four
    engines post `type='accrual'` and take a day-1 mirror; the other two post
    `type='standard'` and **must never reverse**. `depreciation.py` says so in
    capitals — *"a depreciation entry that reversed itself on day 1 would leave
    the plant at its purchase cost forever"*, which `CR-060` §5 measures at
    **$40,000 on one truck** — and `allowance.py` says *"IT IS A BALANCE, NOT AN
    ACCRUAL … carried from month to month"*.

    ⚠ **IT IS SERVED BECAUSE THE ALTERNATIVE IS A LITERAL IN A SCREEN.** A browser
    holding its own four-row table of *which engine reverses* is the shape this
    blueprint names on p019 — *"a literal outlives its list … the row exists, the
    API serves it, `tsc` passes, and the chip never appears"* — one step worse,
    because here the stale literal would be a claim about money.

    ⚠ **AND THE DATE IS `manual_je.accrual_reversal_due_on`, NEVER `end + 1 day`.**
    BR-LED-005 says *day 1 of the next PERIOD* and BR-TEN-022 computes a period
    from the tenant's fiscal year and cadence, so a utility closing QUARTERLY
    accrues into a quarter. `close.period_window` is the one implementation of
    that calendar; adding a day to a date here would be a second one, in a
    browser, on a money path.

    `reverses_on` is `null` for a standard entry — never `""`, never today —
    so a screen draws *Never* from an absence it cannot mistake for a value.
    """
    return {
        "entry_type": models.JE_ACCRUAL if reverses else models.JE_STANDARD,
        "reverses_on": (
            wire.day(manual_je.accrual_reversal_due_on(period_end)) if reverses else None
        ),
    }


def _refused(refusal: unbilled_accrual.UnbilledAccrualError) -> errors.ApiError:
    """One key, with the service's own sentence in `params.detail`.

    The same shape `finance_api._close_refused` uses and for the same reason:
    classifying a prose refusal by searching its text would bind this file to
    another module's sentences, and the first reworded refusal would silently
    change the status code.
    """
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-791 · BR-LED-006",
        message_key="ledger.accrual.refused",
        params={"detail": str(refusal)},
    )


def _service_row(row: unbilled_accrual.ServiceAccrual) -> dict[str, Any]:
    return {
        "service": row.service_code,
        # B14 rule 31 — the GL account travels as an id AND as nothing a screen
        # shows: the label a clerk reads is the service name, and the id is for
        # the drill-back link.
        "ledger_account_id": row.ledger_account_id,
        "quantity": str(row.quantity),
        "unit": row.unit,
        "amount": wire.money(row.amount),
        "account_count": row.account_count,
        "read_count": row.read_count,
        "distinct_unit_prices": row.distinct_unit_prices,
        "problems": list(row.problems),
    }


def _account_row(row: unbilled_accrual.AccountAccrual) -> dict[str, Any]:
    return {
        "account_id": row.account_id,
        "service": row.service_code,
        "quantity": str(row.quantity),
        "unit": row.unit,
        "unit_price": wire.money(row.unit_price),
        "amount": wire.money(row.amount),
        "read_count": row.read_count,
        "estimated_read_count": row.estimated_read_count,
    }


def _preview_dict(preview: unbilled_accrual.UnbilledAccrualPreview) -> dict[str, Any]:
    return {
        "period": {
            "start": preview.period_start.isoformat(),
            "end": preview.period_end.isoformat(),
        },
        # BR-LED-005 — an accrual, and it takes its day-1 mirror. See
        # `_posting_shape`.
        **_posting_shape(reverses=True, period_end=preview.period_end),
        # `null` and 0.00 are DIFFERENT and are kept different — see the module
        # docstring.
        "total": wire.money(preview.total),
        "currency": preview.currency,
        "services": [_service_row(row) for row in preview.services],
        "accounts": [_account_row(row) for row in preview.accounts],
        "account_rows_shown": len(preview.accounts),
        "account_rows_total": preview.account_rows_total,
        "unbilled_ar_account_id": preview.unbilled_ar_account_id,
        "posting_key": preview.posting_key,
        "already_posted_entry_id": preview.already_posted_entry_id,
        "period_is_closed": preview.period_is_closed,
        # Named absences with COUNTS. A screen groups on the code; nobody parses
        # prose (the `apps/billing/delivery_seam.BillDelivery` shape).
        "excluded": dict(preview.excluded),
        "problems": list(preview.problems),
        "unavailable": wire.gaps(preview.unavailable),
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk
def unbilled_accrual_preview(request: Any) -> Response:
    """C2's preview. Params: `from` + `to`, both REQUIRED. Writes nothing."""
    require_tenant(request)
    start, end = _window(request.query_params)
    try:
        preview = unbilled_accrual.preview_unbilled_revenue(period_start=start, period_end=end)
    except unbilled_accrual.UnbilledAccrualError as refusal:
        raise _refused(refusal) from refusal
    return Response(_preview_dict(preview))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-LED-006's gate, EP-LED-05 §8's READING
def post_unbilled_accrual(request: Any) -> Response:
    """C2's post. Body: `from`, `to`, `posted_at` — all REQUIRED.

    The service is the enforcement: the role gate, the closed-period refusal and
    the replay guard are all in `apps/ledger/unbilled_accrual.py`, where a
    caller that is not this endpoint meets them too.
    """
    require_tenant(request)
    body = _payload(request)
    start, end = _window(body)
    try:
        result = unbilled_accrual.accrue_unbilled_revenue(
            _actor(request),
            period_start=start,
            period_end=end,
            posted_at=_moment(body),
        )
    except unbilled_accrual.UnbilledAccrualError as refusal:
        raise _refused(refusal) from refusal
    return Response(
        {
            "entry_id": result.entry_id,
            "posting_key": result.posting_key,
            # `created: false` is the REPLAY, not a failure — a resumed close
            # pressing the button twice is the correct outcome (US-LED-001 TC-6).
            "created": result.created,
            "entry_date": wire.day(result.entry_date),
            "total": wire.money(result.total),
            "line_count": result.line_count,
            "services": [_service_row(row) for row in result.services],
            "preview": _preview_dict(result.preview),
            "unavailable": wire.gaps(result.unavailable),
        },
        status=201 if result.created else 200,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-060 C17 / task T7b — THE UNPAID SUPPLIER COST ACCRUAL
# ═══════════════════════════════════════════════════════════════════════════
def _cost_refused(refusal: unpaid_cost_accrual.UnpaidCostAccrualError) -> errors.ApiError:
    """One key, with the service's own sentence in `params.detail` — the twin of
    `_refused` above, and separate only because the two services raise different
    exception types on purpose (a caller can tell which act was refused without
    matching on prose)."""
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-792 · BR-LED-006",
        message_key="ledger.accrual.refused",
        params={"detail": str(refusal)},
    )


def _cost_account_row(row: unpaid_cost_accrual.CostAccountAccrual) -> dict[str, Any]:
    return {
        # B14 rule 31 — the account is shown by its CODE and NAME, which is what
        # a finance person reads; the id travels for the drill-back link only.
        "ledger_account_id": row.ledger_account_id,
        "code": row.code,
        "name": row.name,
        "amount": wire.money(row.amount),
        "invoice_count": row.invoice_count,
    }


def _unpaid_invoice_row(row: unpaid_cost_accrual.UnpaidInvoice) -> dict[str, Any]:
    return {
        "invoice_id": row.invoice_id,
        "reference": row.reference,
        "supplier_name": row.supplier_name,
        "invoice_date": row.invoice_date.isoformat(),
        "service": row.service,
        "amount": wire.money(row.amount),
        "ledger_account_id": row.ledger_account_id,
        "code": row.code,
    }


def _cost_preview_dict(preview: unpaid_cost_accrual.UnpaidCostPreview) -> dict[str, Any]:
    return {
        "period": {
            "start": preview.period_start.isoformat(),
            "end": preview.period_end.isoformat(),
        },
        # BR-LED-792 — an accrual too, and it reverses on the same day.
        **_posting_shape(reverses=True, period_end=preview.period_end),
        # `null` and 0.00 are DIFFERENT and are kept different: null means the
        # window holds purchases in more than one currency, so no single entry
        # can carry them; 0.00 means nothing captured is unpaid.
        "total": wire.money(preview.total),
        "currency": preview.currency,
        "accounts": [_cost_account_row(row) for row in preview.accounts],
        "invoices": [_unpaid_invoice_row(row) for row in preview.invoices],
        "invoice_rows_shown": len(preview.invoices),
        "invoice_rows_total": preview.invoice_rows_total,
        "accrued_expenses_account_id": preview.accrued_expenses_account_id,
        "posting_key": preview.posting_key,
        "already_posted_entry_id": preview.already_posted_entry_id,
        "period_is_closed": preview.period_is_closed,
        # Named absences with COUNTS — `settled_within_the_period` is the
        # double-count guard, and a clerk who expected nine invoices and sees six
        # needs the number rather than a silence.
        "excluded": dict(preview.excluded),
        "problems": list(preview.problems),
        "unavailable": wire.gaps(preview.unavailable),
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk
def unpaid_cost_accrual_preview(request: Any) -> Response:
    """C17's figure before it posts. Params: `from` + `to`. Writes nothing."""
    require_tenant(request)
    start, end = _window(request.query_params)
    try:
        preview = unpaid_cost_accrual.preview_unpaid_costs(period_start=start, period_end=end)
    except unpaid_cost_accrual.UnpaidCostAccrualError as refusal:
        raise _cost_refused(refusal) from refusal
    return Response(_cost_preview_dict(preview))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-LED-006's gate, EP-LED-05 §8's READING
def post_unpaid_cost_accrual(request: Any) -> Response:
    """C17's post. Body: `from`, `to`, `posted_at` — all REQUIRED.

    The service is the enforcement: the role gate, the closed-period refusal,
    the replay guard and the double-count exclusion all live in
    `apps/ledger/unpaid_cost_accrual.py`, where a caller that is not this
    endpoint meets them too.
    """
    require_tenant(request)
    body = _payload(request)
    start, end = _window(body)
    try:
        result = unpaid_cost_accrual.accrue_unpaid_costs(
            _actor(request),
            period_start=start,
            period_end=end,
            posted_at=_moment(body),
        )
    except unpaid_cost_accrual.UnpaidCostAccrualError as refusal:
        raise _cost_refused(refusal) from refusal
    return Response(
        {
            "entry_id": result.entry_id,
            "posting_key": result.posting_key,
            # `created: false` is the REPLAY, not a failure.
            "created": result.created,
            "entry_date": wire.day(result.entry_date),
            "total": wire.money(result.total),
            "line_count": result.line_count,
            "accounts": [_cost_account_row(row) for row in result.accounts],
            "preview": _cost_preview_dict(result.preview),
            "unavailable": wire.gaps(result.unavailable),
        },
        status=201 if result.created else 200,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-060 C20 / task T7f — DEPRECIATION
# ═══════════════════════════════════════════════════════════════════════════
def _depreciation_refused(refusal: depreciation.DepreciationError) -> errors.ApiError:
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-793 · BR-LED-006",
        message_key="ledger.accrual.refused",
        params={"detail": str(refusal)},
    )


def _depreciation_dict(preview: depreciation.DepreciationPreview) -> dict[str, Any]:
    return {
        "period": {
            "start": preview.period_start.isoformat(),
            "end": preview.period_end.isoformat(),
        },
        # ⚠ **STANDARD, AND IT NEVER REVERSES.** `depreciation.py`: *"IT IS NOT
        # AN ACCRUAL AND IT MUST NEVER BE ONE."*
        **_posting_shape(reverses=False, period_end=preview.period_end),
        # `null` means the asset register publishes no read this charge can be
        # taken from — never confused with 0.00, *"the plant did not
        # depreciate"*, which is a claim about a balance sheet.
        "total": wire.money(preview.total),
        "currency": preview.currency,
        "asset_count": preview.asset_count,
        "assets_considered": preview.assets_considered,
        "expense_account_id": preview.expense_account_id,
        "accumulated_account_id": preview.accumulated_account_id,
        "posting_key": preview.posting_key,
        "already_posted_entry_id": preview.already_posted_entry_id,
        "period_is_closed": preview.period_is_closed,
        "excluded": dict(preview.excluded),
        "problems": list(preview.problems),
        "unavailable": wire.gaps(preview.unavailable),
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk
def depreciation_preview(request: Any) -> Response:
    """C20's charge before it posts. Params: `from` + `to`. Writes nothing."""
    require_tenant(request)
    start, end = _window(request.query_params)
    try:
        preview = depreciation.preview_depreciation(period_start=start, period_end=end)
    except depreciation.DepreciationError as refusal:
        raise _depreciation_refused(refusal) from refusal
    return Response(_depreciation_dict(preview))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def post_depreciation(request: Any) -> Response:
    """C20's *"period trigger"*. Body: `from`, `to`, `posted_at` — all REQUIRED.

    C20 names no endpoint at all — *"a posting path and a period trigger, not a
    calculation"* — and this is the trigger. The amount is not in the body and
    could not be: it comes from the asset register's own figures, and a typed
    figure here would be a second implementation of BR-AST-047 wearing a form.
    """
    require_tenant(request)
    body = _payload(request)
    start, end = _window(body)
    try:
        result = depreciation.post_depreciation(
            _actor(request),
            period_start=start,
            period_end=end,
            posted_at=_moment(body),
        )
    except depreciation.DepreciationError as refusal:
        raise _depreciation_refused(refusal) from refusal
    return Response(
        {
            "entry_id": result.entry_id,
            "posting_key": result.posting_key,
            "created": result.created,
            "entry_date": wire.day(result.entry_date),
            "total": wire.money(result.total),
            "line_count": result.line_count,
            "asset_count": result.asset_count,
            "preview": _depreciation_dict(result.preview),
            "unavailable": wire.gaps(result.unavailable),
        },
        status=201 if result.created else 200,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CR-060 C5 / task T15 — THE ALLOWANCE FOR DOUBTFUL ACCOUNTS (PO 2026-09-03)
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **THESE TWO EXIST BECAUSE `G52` CAUGHT THE SERVICE WITHOUT THEM, AND THE
# GATE WAS RIGHT.** `allowance.estimate_allowance` declares `@require_role` —
# the code's own statement that a PERSON performs it — and for one commit no
# route a person could reach called it. That is hard-won law 2 exactly, and it
# is the same shape this lane had just spent the morning repairing on `CR-060`
# T6(e), where the settlement posting was reachable only with an HTTP client.
#
# C5 names no endpoint, so the SHAPE is taken from the accruals above rather
# than invented: a GET that computes and writes nothing, and a `/post` that
# moves money — Django resolves by URL and not by method, so a POST on the GET's
# own path would SHADOW it (this file's exception 1).
def _allowance_refused(refusal: allowance.AllowanceError) -> errors.ApiError:
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="BR-LED-795 · BR-LED-006",
        message_key="ledger.accrual.refused",
        params={"detail": str(refusal)},
    )


def _allowance_dict(preview: allowance.AllowancePreview) -> dict[str, Any]:
    """`AllowancePreview.as_dict()` plus the two posting facts screen 1·4 draws.

    ⚠ **THE SHAPE IS ADDED HERE AND NOT IN `allowance.as_dict`, DELIBERATELY.**
    That dataclass is the SERVICE's own answer and `close.py` reads it too; the
    `Type` / `Reverses` pair is a WIRE fact for one screen, and putting it on the
    service would make a screen's column part of the engine's contract.

    ⚠ **AND THIS ONE IS `standard`, WHICH IS THE WHOLE RULE.** `allowance.py`:
    *"IT IS A BALANCE, NOT AN ACCRUAL … carried from month to month."* A
    reversing allowance would be zeroed on the first morning of every month.

    ⚠ **THE PERIOD ARRIVES AS A TWO-ELEMENT LIST HERE AND AS AN OBJECT ON THE
    OTHER THREE** — `as_dict` serves `"period": [start, end]`. That is the
    existing contract and it is not changed in this commit; the client types both
    shapes rather than a screen guessing which it got.
    """
    return {**preview.as_dict(), **_posting_shape(reverses=False, period_end=preview.period_end)}


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Finance = R for Staff/Clerk
def allowance_preview(request: Any) -> Response:
    """T15's figure before it posts. Params: `from` + `to`. Writes nothing.

    Answers for a tenant with the policy OFF too, and says so — `enabled:false`,
    `target:null` and the reason on `problems`. That is a state a screen prints,
    never an error a caller has to catch: the DIRECT write-off is a lawful
    accounting policy and is what most utilities this size will keep.
    """
    require_tenant(request)
    start, end = _window(request.query_params)
    try:
        preview = allowance.preview_allowance(period_start=start, period_end=end)
    except allowance.AllowanceError as refusal:
        raise _allowance_refused(refusal) from refusal
    return Response(_allowance_dict(preview))


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # BR-LED-006's gate, EP-LED-05 §8's READING
def post_allowance(request: Any) -> Response:
    """T15's post. Body: `from`, `to`, `posted_at` — all REQUIRED.

    The service is the enforcement: the role gate, the policy switch, the
    unreadable-ageing refusal and the replay guard all live in
    `apps/ledger/allowance.py`, where a caller that is not this endpoint meets
    them too.

    ⚠ **A MOVEMENT OF ZERO ANSWERS `200` WITH NO `entry_id`, AND THAT IS NOT AN
    ERROR.** The allowance already stands at the computed target, so nothing is
    posted — an entry of 0.00 would say nothing and would spend the period's
    posting key. `direction` says which of the three happened.
    """
    require_tenant(request)
    body = _payload(request)
    start, end = _window(body)
    try:
        result = allowance.estimate_allowance(
            _actor(request),
            period_start=start,
            period_end=end,
            posted_at=_moment(body),
        )
    except allowance.AllowanceError as refusal:
        raise _allowance_refused(refusal) from refusal
    return Response(
        {
            "entry_id": result.entry_id,
            "posting_key": result.posting_key,
            # `created: false` is the REPLAY or the no-movement case, never a
            # failure — `direction` tells them apart.
            "created": result.created,
            "direction": result.direction,
            "entry_date": wire.day(result.entry_date),
            "target": wire.money(result.target),
            "standing_before": wire.money(result.standing_before),
            "movement": wire.money(result.movement),
            "preview": _allowance_dict(result.preview),
        },
        status=201 if result.created else 200,
    )


urlpatterns = [
    path("finance/accruals/unbilled", unbilled_accrual_preview),
    path("finance/accruals/unbilled/post", post_unbilled_accrual),
    # C17 asks for `POST /finance/accruals/unpaid-costs`. Django resolves by URL
    # and not by method, so the write is `/post` — the same exception this file
    # already records for C2 and `journal_api.py` for the draft JE.
    path("finance/accruals/unpaid-costs", unpaid_cost_accrual_preview),
    path("finance/accruals/unpaid-costs/post", post_unpaid_cost_accrual),
    path("finance/depreciation", depreciation_preview),
    path("finance/depreciation/post", post_depreciation),
    # CR-060 C5 / task T15 — the GET computes, the /post moves money. Same
    # split as the two accruals above, for the same routing reason.
    path("finance/allowance", allowance_preview),
    path("finance/allowance/post", post_allowance),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C2 + task T7 (12-governance/11-change-requests.md §7 · §12) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-005/006/791 ·
#         CLAUDE.md rules 1, 2, 5, 6, 7
# generated: 2026-09-02 by the CR-060 T7 lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(C2 names two endpoints and NO screen, and no
#         §12 task row owns one — REPORTED rather than invented) F✔ G✔
#         H=deferred(🔒 HUMAN-REVIEW-PENDING — the service is the sensitive path
#         and carries the review-ledger row)
# gates: see 06-backend/tests/test_cr060_t7_unbilled_accrual.py
# exceptions: (1) **C2 ASKS FOR `POST /finance/accruals/unbilled` ON THE SAME
#         PATH AS THE GET, AND THAT IS NOT HOW THIS PRODUCT ROUTES.** Django
#         resolves by URL and not by method, and registering one path twice
#         shadows the first — the exact precedent `journal_api.py` records for
#         `POST /ledger/journal-entries/drafts` beside a GET-only
#         `ledger/journal-entries`. The write is therefore
#         `POST /finance/accruals/unbilled/post`. REPORTED · (2) ONE NEW MESSAGE
#         KEY, `ledger.accrual.refused`, is owed in the eleven locale catalogues
#         and is REPORTED for the locale lane rather than landed here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
