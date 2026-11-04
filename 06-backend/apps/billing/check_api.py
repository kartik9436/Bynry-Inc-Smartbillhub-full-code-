# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check) · US-BIL-038 (Calculate)
# Plan:     15-bulk-bill-run-build-plan.md A3 (Check job: start, progress,
#           resume) · A4 (findings: categories → tags with counts; one tag's
#           accounts paged and searchable with their other tags; Ready to bill)
#           · A5 (decisions: a tag, an account, a selection) · A6 (re-check
#           selected) · A7 (Calculate: `POST …/calculate` with
#           `background: true` already answers 202 + the poll address; its
#           progress is the job record — nothing new was needed)
# Rules:    BR-BIL-1052 · BR-BIL-1053 · BR-BIL-1040 (as amended 2026-09-30) ·
#           OQ-843 re-ruled (option C) · NFR-3 (every list pages)
# Tests:    06-backend/tests/test_bbr_check_store.py (API cases, isolation)
# ───────────────────────────────────────────────────────
"""The redrawn Check step's HTTP surface. New file, so `api.py` only mounts it.

Every READ here is a query over the SAVED results (`check_store`), after a
staleness sweep that re-checks exactly the accounts whose plan, reading,
meter or payment moved since they were checked (`check_staleness`) — never a
re-run of the whole pass on a GET. Every WRITE is AdminOrClerk; every read is
any tenant role (A4). A run of another tenant is the same 404 as a run that
does not exist (`selectors.run_or_404`).
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from django.db import transaction
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import (
    check_staleness,
    check_store,
    decisions,
    gather,
    run_jobs,
    runs,
    selectors,
)
from apps.billing.exceptions import BillingRuleError
from core import errors
from core import jobs as core_jobs
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

logger = logging.getLogger("smartbillhub.billing")


def _billing_api() -> Any:
    from apps.billing import api

    return api


def _payload(request: Any) -> dict[str, Any]:
    return _billing_api()._payload(request)


def _actor_id(request: Any) -> Any:
    return _billing_api()._actor_id(request)


def _refusal(refusal: BillingRuleError, br_ref: str = "BR-BIL-1052") -> errors.BizError:
    return _billing_api()._as_catalog_refusal(refusal, br_ref)


def _ids(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="billing.payload_not_object")
    out = []
    for one in value:
        try:
            out.append(str(uuid.UUID(str(one))))
        except (TypeError, ValueError):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="billing.payload_not_object"
            ) from None
    return out


def _quantity(value: Any) -> Decimal | None:
    """A typed quantity as `Decimal`, never `float`; absent is None (a
    different fact from zero). Refused by field when it is not a number."""
    if value is None or value == "":
        return None
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        quantity = None
    if quantity is None or not quantity.is_finite():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.amount_invalid",
            field_errors=[{"field": "amount", "code": errors.VAL_FORMAT}],
        )
    return quantity


def _categories(value: Any) -> list[str] | None:
    """A re-check's `categories` — None (the full check) or known names only."""
    from apps.billing import check_engine

    if value is None:
        return None
    if (
        not isinstance(value, list)
        or not value
        or any(str(one) not in check_engine.CATEGORIES for one in value)
    ):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.check.unknownCategory",
            params={"allowed": sorted(check_engine.CATEGORIES)},
        )
    return sorted({str(one) for one in value})


def _stop_response(stop: runs.UtilityWideStop) -> Response:
    """B21 — a utility-wide stop: what, who, the support reference; run kept.

    ⚠ **IN THE ERROR ENVELOPE, NOT BESIDE IT (DEF-BIL-8510, DEF-BIL-8580).** The body was
    `{stopped, stop}` alone, and the screen's API client reads a failure's
    `message_key` from the TOP of the body — so a real stop reached the clerk
    as the client's generic *unexpected error*, with no module named and a
    reference that was not the one in the log. The component test never saw
    it because its fake answered in the envelope shape the server did not
    (hard-won law 2: a fixture that cannot tell a working answer from a broken
    one). The envelope names WHAT (`billing.bulkRun.check.down.<module>`), WHO
    (`params.who`), and carries the stop's own reference as the trace id so
    the screen's *Ref 73FB-C9D7* is the log's `SBH-73FBC9D7`. `stop` stays for
    every reader that already used it."""
    payload = stop.as_dict()
    return Response(
        {
            "code": errors.SYS_PROVIDER,
            "message_key": f"billing.bulkRun.check.down.{stop.module}",
            "params": {"module": stop.module, "who": stop.who, "ref": stop.support_ref},
            "field_errors": [],
            "br_ref": "BR-BIL-1052",
            "trace_id": str(stop.support_ref).split("-", 1)[-1].lower(),
            "stopped": True,
            "stop": payload,
        },
        status=503,
    )


# ── A3 · start / progress / resume ──────────────────────────────────────────
@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def run_check(request: Any, run_id: str) -> Response:
    """`POST` starts the Check (or re-checks `account_ids` — A6); `GET` is its
    progress: the saved counts, the job's record, and any utility-wide stop."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    if request.method == "GET":
        summary = dict(run.findings_summary or {})
        job = None
        resumed = False
        if summary.get("job_id"):
            try:
                job = core_jobs.current(summary["job_id"])
            except core_jobs.JobsError:
                job = None
        if (
            job is not None
            and job["status"] == core_jobs.RUNNING
            and run_jobs.job_is_abandoned(job["id"])
        ):
            # DEF-BIL-8511 / F1 — the worker died mid-Check. The screen polls
            # this read, so the run carries on by itself within a poll or two
            # of the workers saying so, instead of after the broker's 8,820 s.
            try:
                job, outcome = run_jobs.resume_job(run, job["id"])
                resumed = outcome == core_jobs.REDISPATCHED
            except BillingRuleError:
                job = core_jobs.current(summary["job_id"])
        return Response(
            {
                "bill_run_id": str(run.pk),
                "counts": check_store.counts(run),
                "stop": summary.get("stop"),
                "job": (
                    None
                    if job is None
                    else {
                        "id": job["id"],
                        "status": job["status"],
                        "progress": job.get("progress"),
                        "error": job.get("error"),
                        "resumed": resumed,
                    }
                ),
            }
        )
    if not AdminOrClerk().has_permission(request, None):
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-SHL-025")
    payload = _payload(request)
    only = _ids(payload.get("account_ids"))
    background = payload.get("background", True) is True
    try:
        check_store.refuse_if_sent(run)
    except BillingRuleError as refusal:
        raise _refusal(refusal) from refusal
    if background:
        ready, reason = run_jobs.would_run()
        if ready:
            record = run_jobs.enqueue_check(
                run, only_accounts=only, actor_user_id=_actor_id(request)
            )
            if only is None:
                # DEF-BIL-9004 — name the job on the run NOW, not when a worker
                # first picks it up (`check_batches._point_summary_at`). Until
                # then `GET …/check` answered `job: null` (or the previous,
                # finished job on Check again) and the screen drew the saved
                # counts with Price enabled — 20 s and more at 40,015 accounts.
                summary = dict(run.findings_summary or {})
                summary["job_id"] = str(record["id"])
                summary["stop"] = None
                run.findings_summary = summary
                run.save(update_fields=["findings_summary", "updated_at"])
            return Response(
                {**core_jobs.accepted(record), "bill_run_id": str(run.pk), "background": True},
                status=202,
            )
        try:
            run_jobs.refuse_if_no_worker(run, reason=reason)
        except BillingRuleError as refusal:
            raise _refusal(refusal, "BR-BIL-051") from refusal
    try:
        summary = check_store.check_run(run, only_accounts=only)
    except runs.UtilityWideStop as stop:
        return _stop_response(stop)
    except BillingRuleError as refusal:
        raise _refusal(refusal) from refusal
    return Response(
        {"bill_run_id": str(run.pk), "background": False, "counts": summary}, status=200
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_check_resume(request: Any, run_id: str) -> Response:
    """A3 — resume a Check job that stopped (a worker lost, a utility-wide
    stop cleared). It carries on after the last account it saved."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    job_id = (run.findings_summary or {}).get("job_id")
    if not job_id:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-BIL-052", message_key="billing.check.nothingToResume"
        )
    # DEF-BIL-8511 — back to the WORKER, never the rest of the Check in this
    # request (60 s). A job still being worked, or already waiting for a
    # worker, is left alone and said so.
    try:
        record, outcome = run_jobs.resume_job(run, job_id)
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-051") from refusal
    if outcome != core_jobs.REDISPATCHED:
        return Response(
            {"job_id": job_id, "status": record.get("status"), "resumed": False, "why": outcome}
        )
    return Response({**core_jobs.accepted(record), "resumed": True}, status=202)


# ── A4 · findings ───────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def run_check_findings(request: Any, run_id: str) -> Response:
    """Categories → tags with counts (no `tag`), ONE tag's accounts (`tag=`),
    the Ready list (`list=ready`), or ONE account's every problem
    (`account=`). A staleness sweep runs first (OQ-843 option C)."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    params = request.query_params
    # `DEF-BIL-10709` (tester L3-07) — `sweep=0` skips the sweep. A pane sweeps
    # ONCE when it opens and sends `sweep=0` for its next page and every
    # keystroke of its search: sweeping on each one made typing look ignored
    # (the rows arrived after the sweep, seconds late) while the beat entry
    # already sweeps every open run every 60 seconds. Absent = sweep, so every
    # other caller is unchanged.
    swept = {"stale": 0, "rechecked": 0, "background": False}
    if str(params.get("sweep", "")) != "0":
        try:
            swept = check_staleness.sweep(run, actor_user_id=_actor_id(request))
        except runs.UtilityWideStop as stop:
            return _stop_response(stop)
        except BillingRuleError:
            swept = {"stale": 0, "rechecked": 0, "background": False}
    if params.get("account"):
        found = check_store.account_findings(run, str(params.get("account")))
        if found is None:
            raise errors.NotFoundError()
        return Response({**found, "swept": swept})
    if params.get("tag"):
        return Response(
            {**check_store.tag_accounts(run, str(params.get("tag")), params), "swept": swept}
        )
    if params.get("list") == "ready":
        return Response({**check_store.ready_accounts(run, params), "swept": swept})
    return Response({**check_store.findings_summary(run), "swept": swept})


# ── A5 · decisions ──────────────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_check_decide(request: Any, run_id: str) -> Response:
    """Answer ONE tag: for all its accounts (`scope: "all"` — the standing
    answer), or for named accounts (`scope: "accounts"`, `account_ids`, and
    `service_code` where the case is per service). An account's own answer
    always beats its tag's. Accepting a suggestion is `choice:
    "accept_suggestion"`."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    case = str(payload.get("case") or "")
    choice = str(payload.get("choice") or "")
    scope = payload.get("scope") or "accounts"
    offered = decisions.CHOICES_BY_CASE.get(case)
    if not offered or choice not in offered:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.check.choiceNotOffered",
            params={"case": case, "choice": choice},
        )
    try:
        if scope == "all":
            decisions.set_standing_answer(
                bill_run=run, case=case, choice=choice, decided_by=getattr(request, "user", None)
            )
            return Response({"case": case, "choice": choice, "scope": "all"}, status=201)
        ids = _ids(payload.get("account_ids")) or []
        if not ids:
            raise errors.ValidationError(
                errors.VAL_REQUIRED, message_key="billing.check.noAccounts"
            )
        service_id = None
        if payload.get("service_code"):
            codes = gather._resolve("tenancy", "service_ids_by_code")
            service_id = ((codes() if codes else {}) or {}).get(str(payload["service_code"]))
        bulk = uuid.uuid4() if len(ids) > 1 else None
        rows = [
            decisions.record_decision(
                bill_run=run,
                account_id=account_id,
                case=case,
                choice=choice,
                reason=payload.get("reason"),
                # DEF-BIL-8551 / DEF-BIL-8415 — an Estimate is the clerk's
                # typed quantity WITH its unit (BR-BIL-015, CLAUDE.md rule 3);
                # `record_decision` refuses one without either, by that rule.
                amount=_quantity(payload.get("amount")),
                unit=(str(payload.get("unit") or "").strip() or None),
                service_id=service_id,
                decided_by=getattr(request, "user", None),
                bulk_action_id=bulk,
            )
            for account_id in ids
        ]
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-015") from refusal
    return Response(
        {
            "case": case,
            "choice": choice,
            "scope": "accounts",
            "recorded": len(rows),
            "bulk_action_id": None if bulk is None else str(bulk),
        },
        status=201,
    )


# ── A6 · re-check selected ─────────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_check_recheck(request: Any, run_id: str) -> Response:
    """Re-check NAMED accounts only (B15). Up to `INLINE_RECHECK` inline; more
    go to the billing queue. `categories` (optional, DEF-BIL-8286) re-runs only
    those categories of the Check and what is downstream of them."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    ids = _ids(payload.get("account_ids")) or []
    if not ids:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="billing.check.noAccounts")
    categories = _categories(payload.get("categories"))
    try:
        check_store.refuse_if_sent(run)
    except BillingRuleError as refusal:
        raise _refusal(refusal) from refusal
    if len(ids) > check_staleness.INLINE_RECHECK:
        record = run_jobs.enqueue_check(
            run, only_accounts=ids, actor_user_id=_actor_id(request), categories=categories
        )
        return Response({**core_jobs.accepted(record), "background": True}, status=202)
    try:
        check_store.check_run(run, only_accounts=ids, categories=categories)
    except runs.UtilityWideStop as stop:
        return _stop_response(stop)
    except BillingRuleError as refusal:
        raise _refusal(refusal) from refusal
    return Response({"rechecked": len(ids), "background": False, "counts": check_store.counts(run)})


# ── B14 · inline fixes (DEF-BIL-8218) ─────────────────────────────────────
@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_check_fix(request: Any, run_id: str) -> Response:
    """Write ONE fact the clerk supplies on a blocked row through the module
    that owns it (`check_fixes.FIXES`), then re-check that account. Body:
    `{account_id, fix, …the fix's values}`. Answers the account after it."""
    from apps.billing import check_fixes

    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    account_id = (_ids([payload["account_id"]]) or [None])[0] if payload.get("account_id") else None
    if account_id is None:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="billing.check.noAccounts")
    user = getattr(request, "user", None)
    actor = SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )
    try:
        answer = check_fixes.apply_fix(
            run,
            account_id=account_id,
            fix=str(payload.get("fix") or ""),
            payload=payload,
            actor=actor,
        )
    except runs.UtilityWideStop as stop:
        return _stop_response(stop)
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-1052") from refusal
    return Response(answer, status=200)


# ── B18 / A9 · leave a ready account out, put it back (DEF-BIL-8217) ──────
def _left_out_answer(request: Any, run_id: str, act: str) -> Response:
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    ids = _ids(payload.get("account_ids")) or []
    if not ids:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key="billing.check.noAccounts")
    user = getattr(request, "user", None)
    try:
        with transaction.atomic():
            for account_id in ids:
                if act == "leave_out":
                    check_store.leave_out(
                        run, account_id, decided_by=user, reason=payload.get("reason")
                    )
                else:
                    check_store.put_back(run, account_id, decided_by=user)
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-1054") from refusal
    return Response(
        {"done": act, "account_ids": ids, "counts": check_store.counts(run)}, status=201
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_leave_out(request: Any, run_id: str) -> Response:
    """BR-BIL-1054 — leave READY accounts out of this run (`account_ids`). They
    join Not in this run and, at Send, Pending billing as *left out by clerk*.
    All or nothing: one account that is not ready refuses the request."""
    return _left_out_answer(request, run_id, "leave_out")


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_put_back(request: Any, run_id: str) -> Response:
    """BR-BIL-1054 — put left-out accounts back into this run."""
    return _left_out_answer(request, run_id, "put_back")


# ── B19 / A8 · Sign off's figures (DEF-BIL-8220) ──────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def run_sign_off_summary(request: Any, run_id: str) -> Response:
    """Who is billed (accounts and units, each adding back to Scope's figure),
    usage and charges per service with the other categories, payments and
    balances with how the amount due will be paid, by customer type, waived."""
    from apps.billing import signoff

    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(signoff.sign_off_summary(run))


# ── B20 / A9 · Not in this run, leave for next cycle (DEF-BIL-8223) ───────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def run_not_in_run(request: Any, run_id: str) -> Response:
    """Every account the run does not bill and every unit it cannot, paged;
    `group=` presses a filter (Sign off's *See* opens it this way)."""
    from apps.billing import not_in_run

    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(not_in_run.not_in_run(run, request.query_params))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_leave_for_next_cycle(request: Any, run_id: str) -> Response:
    """Mark accounts this run left in Pending billing for the NEXT cycle
    (`account_ids`, and `at` — the clerk's event time, BR-TEN-043)."""
    from datetime import datetime

    from apps.billing import pending

    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    ids = _ids(payload.get("account_ids")) or []
    try:
        at = datetime.fromisoformat(str(payload.get("at") or ""))
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="billing.notInRun.atRequired"
        ) from None
    try:
        marked = pending.leave_for_next_cycle(
            bill_run=run, account_ids=ids, at=at, actor=getattr(request, "user", None)
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal, "BR-BIL-1054") from refusal
    return Response({"marked": marked, "account_ids": ids}, status=200)


# ── the Check report (PO ruling 2026-09-30) ────────────────────────────────
@api_view(["GET"])
@permission_classes([AdminOrClerk])
def run_check_report(request: Any, run_id: str) -> Response:
    """The run's read-only Check report — tiles, tags, and each account's
    problems, paged; for a sent run, exactly as at Send."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(check_store.check_report(run, request.query_params))


# ── F4 · who else has this run open (DEF-BIL-8512) ────────────────────────
@api_view(["POST"])
@permission_classes([AnyTenantRole])
def run_presence(request: Any, run_id: str) -> Response:
    """The screen's heartbeat: *I have this run open* — answered with who else
    has (`others`, names only). A courtesy, never a lock (`run_presence`)."""
    from apps.billing import run_presence as presence

    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(
        {
            "others": presence.touch(run, getattr(request, "user", None)),
            "heartbeat_seconds": presence.HEARTBEAT_SECONDS,
        }
    )


urlpatterns = [
    path("billing/runs/<str:run_id>/check", run_check),
    path("billing/runs/<str:run_id>/presence", run_presence),
    path("billing/runs/<str:run_id>/check/report", run_check_report),
    path("billing/runs/<str:run_id>/check/resume", run_check_resume),
    path("billing/runs/<str:run_id>/check/findings", run_check_findings),
    path("billing/runs/<str:run_id>/check/decisions", run_check_decide),
    path("billing/runs/<str:run_id>/check/recheck", run_check_recheck),
    path("billing/runs/<str:run_id>/check/fix", run_check_fix),
    path("billing/runs/<str:run_id>/check/leave-out", run_leave_out),
    path("billing/runs/<str:run_id>/check/put-back", run_put_back),
    path("billing/runs/<str:run_id>/sign-off-summary", run_sign_off_summary),
    path("billing/runs/<str:run_id>/not-in-run", run_not_in_run),
    path("billing/runs/<str:run_id>/not-in-run/leave-for-next-cycle", run_leave_for_next_cycle),
]
