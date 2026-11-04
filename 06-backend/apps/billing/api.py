# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-025 (GET /invoices — the S30 All-bills list, its search,
#           filters, sorts and header roll-up; and, with `f.account_id`, the
#           S21 Bills tab) · US-BIL-026 (GET /invoices/{id} — the bill detail:
#           stamped lines, the A19 summary, the correction chain) ·
#           US-BIL-001 (POST /billing/runs — S31 step 1's idempotent run) ·
#           US-BIL-002 (GET /billing/runs/{id}/findings — S31.2) ·
#           US-BIL-003 (GET /billing/runs/{id}/exceptions + .../resolve — S31.3)
#           · CR-029 RC-W4b (GET /billing/runs — SET-07D's Runs tab, the run
#           history; B17 §4)
#           Screens: S30 · S21 · S31 · S31.2 · S31.3 · SET-07D (Runs)
# Rules:    BR-BIL-004 (issued history is IMMUTABLE — this surface serves no
#           write verb on a bill at all) · BR-BIL-010 (a line shows the GL
#           stamped at issue) · BR-BIL-024 (the due date derives from the bill
#           date) · BR-BIL-070 (the bill date a clerk types on S31 step 1 is
#           STORED and USED — it is the run's service date; PO 2026-08-11,
#           OQ-122 option A) · BR-BIL-026 (the pinned
#           template version, and why issue is not served) · BR-BIL-030 (the
#           document instance is locked at issue) · BR-BIL-031 (payload_version
#           is its own axis) · BR-BIL-063 (the number is allocated at DRAFT
#           creation) · BR-BIL-005 (a run is idempotent; a repeat is 409 with
#           who/when/link) · BR-BIL-015 (a missing read is a CHOICE) ·
#           BR-BIL-003 (a late-fee waiver is manual, never bulk) · BR-BIL-040
#           (a finding is placed by the STAGE the server computed) · BR-BIL-050
#           (the run row is what every later phase hangs off) · BR-BIL-060
#           (bulk everywhere — N rows, one bulk_action_id) · BR-SHL-011 (list
#           grammar q/sort/dir/page/per/f.<name> via BE-05) · BR-SHL-025 /
#           BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1 (cross-tenant
#           reads as absent) · BR-TEN-043 (event-time law — why `past_due` is
#           not computed here, and why issue cannot be served at all)
# Tests:    06-backend/tests/test_us_bil_025_026_bills_read.py ·
#           06-backend/tests/test_us_bil_001_003_run_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json (the committed contract snapshot
#           moves with any endpoint added here — BE-11 TC05) · 07-frontend
#           BillsListPage / BillDetailPage / the S21 Bills tab, and
#           BillRunWizard (S31), all of which were calling these paths against
#           a 404
# ───────────────────────────────────────────────────────
"""billing API endpoints per A11 as amended by 11b §2.8 (+ §2.8a/§2.8b bodies).

THIN by law (B8/LAW 0): every read goes through selectors, every write through a
service, no ORM here, and every refusal is a catalog exception rendered by the
BE-02 handler (G9) — including the ones the service layer raises as
`BillingRuleError`, which is translated at this boundary and nowhere else (see
`_as_catalog_refusal`). READS are open to all three tenant roles — A4 gives
Executive View on "Reads & Billing runs" — so `AnyTenantRole` gates them;
WRITES are `AdminOrClerk`, because that same A4 row gives the Executive VIEW and
BR-SHL-025 is server-enforced rather than a disabled button.

WHY THIS FILE EXISTS TODAY AND NOT A WEEK AGO. It was a one-line docstring with
no `urlpatterns` while `07-frontend/src/features/billing/` shipped S30's list,
S30's detail and the S21 Bills tab against it. The screens rendered a
plain-language failure derived from the 404 — deliberately derived, so it would
stop the day the route landed (hard-won law 1). This is that day; the route
being genuinely REACHABLE is asserted through the real root URLconf in
`test_us_bil_025_tc1__the_invoice_routes_are_actually_mounted`, because an
`api.py` that exports `urlpatterns` no URLconf includes is not an endpoint.

The same thing happened to S31 one day later and is fixed the same way: the
bill-run wizard shipped calling five `/billing/runs…` paths that nothing served,
its steps 2 and 3 rendered their shape with no contents, and four of those five
now land here (the fifth cannot be served honestly — the block above the run
views says exactly why, and 11b §2.8b records it).

The 11b §2.8 rows this slice serves, and the ones it deliberately does not:

    GET  /invoices        US-BIL-025   S30 list + roll-up · S21 tab
    GET  /invoices/{id}   US-BIL-026   S30 detail
    POST /billing/runs    US-BIL-001   S31 step 1 — the idempotent run row
    GET  /billing/runs    CR-029 RC-W4b  SET-07D's Runs tab — the run history
                          (added 2026-08-23; RC-W3b skipped it because this
                          file was a live sibling lane's, hard-won law 11)
    GET  /billing/runs/{id}/findings    US-BIL-002   S31.2
    GET  /billing/runs/{id}/exceptions  US-BIL-003   S31.3
    POST /billing/runs/{id}/exceptions/{caseId}/resolve  US-BIL-003

    NOT here, and NOT stubbed — a route that answers 501 is a promise:
      · GET  /invoices/{id}/document    the pinned render (BR-BIL-026).
        CORRECTED 2026-08-11 — this said "the template tables are r10 #4 and do
        not exist, so nothing could be rendered", and something CAN be rendered
        now: `apps/billing/documents.render_invoice` produces the document from
        the pinned version and the locked instance, and issue refuses a bill
        that cannot (BR-BIL-033). What is still true is that the template TABLES
        do not exist, so one built-in layout stands in for the tenant's own
        body. The ROUTE is unmounted either way — mounting it is this file's
        work, not the renderer's — so the detail still serves
        `document_url: null` rather than a link to a route nobody mounted.
      · GET  /invoices/{id}/deliveries  CORRECTED 2026-08-11 — the queue HAS
        a table (`outbound_messages`, r12 #16) and issue writes one row per bill
        per channel into it. This ROUTE is still US-BIL-024's (S30's delivery
        dashboard reads them), which is why the detail's `deliveries` is null,
        not [].
      · POST /invoices/{id}/void        US-BIL-027, W5 — and its consequence
        message is server-computed (BR-BIL-009), so a route without the
        reversal behind it would state a consequence it cannot honour.
      · ~~GET /billing/pending~~ — **SERVED** (`billing_pending`, US-BIL-006).
        It sat in this list after it was mounted; corrected 2026-08-31 with the
        two below, because a NOT-SERVED list that names a served route sends the
        next reader to build a second one.
      · the CORRECTION rows of §2.8 — their own stories, their own waves.

⚠ **THIS PARAGRAPH SAID `GET /billing/runs/{id}` IS STILL NOT SERVED, AND EVERY
CLAUSE OF IT HAS EXPIRED — CORRECTED 2026-08-31 (CR-051 task 4, hard-won law
1).** It read: *"The run-status POLL watches a background batch that does not
exist (TD-17), and the list added above is SET-07D's history, not a per-run
status. A caller reaching for one run's state gets a list of every run in its
cycle."*

**BOTH HALVES ARE FALSE, and they became false on different days.** The ROUTE is
mounted — `path("billing/runs/<str:run_id>", run_item)`, CR-051 task 1 — and it
was never only a poll: re-opening a finished run is the reason S31 can be
resumed at all, which has nothing to do with asynchrony. And the BACKGROUND
BATCH is real: `apps/billing/run_jobs.py` registers three job kinds
(`billing.run.calculate`, `.findings`, `.issue`), each of which now rides
billing's OWN named queue.

⚠ **AND THE TRUE SENTENCE TODAY IS NARROWER THAN "A WORKER EXISTS", WHICH IS
WHY THIS IS REWRITTEN RATHER THAN DELETED.** Since CR-051 task 29 there are TWO
queues: billing's three kinds are routed to `billing` and drained by the
`celery-billing` service, everything else stays on `celery`. So *"is any worker
alive"* is no longer the same question as *"will this run's job execute"* — a
healthy default worker answers a broadcast ping while the `billing` queue has
no consumer at all. Every caller here asks the narrow question through
`run_jobs.would_run()` → `core.jobs.dispatch_is_ready(CALCULATE_JOB)`, which
resolves the KIND to its queue and asks `active_queues()` about that queue by
name. A lane that reaches for the old broadcast probe re-opens DEF-320.

NO WRITE VERB IS SERVED ON AN INVOICE PATH. BR-BIL-004 / HR-4 / 11b G8: there is
no PUT, PATCH or DELETE on an issued invoice or line anywhere in this API, and a
forged one is refused by the router with a 405 before any view runs. The two
POSTs this file does serve write a `bill_runs` row and a `bill_run_decisions`
row — neither is a bill, and neither touches one.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import logging

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import (
    decisions,
    models,
    one_time,
    one_time_answer,
    pending,
    release,
    run_jobs,
    runs,
    selectors,
    send_batches,
    shadow_report,
    templates_service,
)
from apps.billing import check_api  # bulk bill run A3–A6 — mounted at the foot of urlpatterns
from apps.billing import one_time_send as one_time_send_module
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from apps.billing.gather import GatherProblem
from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core import jobs as core_jobs
from rest_framework.utils.urls import replace_query_param  # noqa: E402 — see `_page_envelope`

from core.pagination import StandardPagination, clamp_page_size, parse_list_params
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

logger = logging.getLogger("smartbillhub.billing")


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="billing.payload_not_object")
    return data


def _actor_id(request: Any) -> Any:
    """WHO is acting, from the SESSION user — never from the body.

    `bill_runs.run_by` and `bill_run_decisions.decided_by` are the evidence
    half of BR-BIL-005 and US-BIL-003 (*"who ran the original"*, *"who made
    that call"*), so the one thing they must not be is client input.
    """
    user = getattr(request, "user", None)
    return getattr(user, "id", None) or getattr(user, "pk", None)


def _date_field(payload: dict[str, Any], name: str) -> date:
    """An ISO calendar date, or a refusal naming the field.

    `date.fromisoformat` and nothing looser: a run's period feeds the
    idempotency key and every B4.3 proration, and a date parsed by guessing at
    a format would put two different runs under one key in one region and not
    in another (BR-TEN-020).
    """
    raw = payload.get(name)
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


def _optional_date_field(payload: dict[str, Any], name: str) -> date | None:
    """`_date_field` for a field a caller may legitimately omit.

    ABSENT, `null` and `""` are all ONE answer — *nobody typed one* — and that
    is a real fact the run stores as NULL (BR-BIL-070). An empty string arrives
    from a date input a clerk cleared, and treating it as a parse failure would
    refuse a run over a field the ruling makes optional.

    A value that IS present is parsed with the same strictness as a required
    one: a bill date decides which tariff version prices the run (BR-RAT-007),
    so a date parsed by guessing at a format would price two identical runs
    differently in two regions (BR-TEN-020).
    """
    raw = payload.get(name)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    return _date_field(payload, name)


def _optional_due_days(payload: dict[str, Any]) -> int | None:
    """CR-029 D9 — S31 step 1's due-days OVERRIDE, or *nobody typed one*.

    PO, verbatim 2026-08-23: *"when we configure Cycle we are provideing default
    values; mostly it wil remain as it is but user can over ride them during
    billing"*. The cycle carries the default (`cycles.due_days`) and this is the
    run's override; `runs.effective_due_days` is the precedence, expressed once.

    ⚠ **ABSENT, `null` AND `""` ARE ONE ANSWER AND `0` IS A DIFFERENT ONE.**
    `due_days = 0` is a lawful arrangement — due ON the bill date, and
    BR-MET-009 requires only `due_days ≥ 0` — so this returns `0`, never `None`,
    for a typed zero. A truthiness test here would silently hand every customer
    in the run the cycle's terms instead of the clerk's.

    A value that cannot be read as a whole number of days is REFUSED rather than
    dropped: a due date decides when a late fee starts (BR-BIL-001), and a
    dropped override is a clerk watching their own number vanish while the bill
    quietly uses another one. Negative is refused for the same reason
    `issue.derive_due_date` refuses it — every bill in the run would be overdue
    on the day it was sent.

    **THE REFUSAL SAYS `billing.run.due_days_invalid`** — *"Enter a whole number
    of days, zero or more."* — in all eleven catalogues (RC-W3c minted it,
    RC-W5-T5 pointed this call site at it). It borrowed
    `metering.cycle.due_days_range` for exactly as long as the sentence did not
    exist: G32 is a zero-baseline ratchet that blocks an unkeyed refusal, a new
    key obliges eleven translations under G15, and the locale files belonged to
    another lane at the time. The stopgap was stated here and REPORTED rather
    than hidden, and this is the line that closed it.
    """
    raw = payload.get("due_days")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    if isinstance(raw, bool):  # `True` is an int in Python and is not a day count
        value = None
    else:
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            value = None
        else:
            if str(raw).strip() != str(value):  # 1.5, "14 days", " 14x"
                value = None
    if value is None or value < 0:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="billing.run.due_days_invalid",
            field_errors=[
                {
                    "field": "due_days",
                    "code": errors.VAL_RANGE,
                    "message_key": "billing.run.due_days_invalid",
                }
            ],
        )
    return value


def _query_date(request: Any, name: str) -> date:
    """A REQUIRED ISO date from the query string — never a server clock.

    BR-TEN-043 and gate G6: *today* belongs to the tenant, not to the process.
    A queue whose ages came from `date.today()` would age its rows by a day the
    moment somebody opened it from another timezone, and an escalation is a
    figure a clerk acts on. So the parameter is required and its absence is a
    refusal naming it, rather than a default that is quietly wrong.
    """
    raw = request.query_params.get(name)
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.pending.as_of_required",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


def _query_int(request: Any, name: str, *, default: int) -> int:
    """An optional whole number from the query string, or the caller's default."""
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.pending.escalation_days_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem
    if value < 0:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="billing.pending.escalation_days_invalid",
            field_errors=[{"field": name, "code": errors.VAL_RANGE}],
        )
    return value


def _decimal_field(payload: dict[str, Any], name: str) -> Decimal | None:
    """A money/quantity value as `Decimal`, never `float` (CLAUDE.md rule 2).

    Absent ⇒ None, which is a different fact from zero and is what a decision
    with no amount carries.
    """
    raw = payload.get(name)
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.amount_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


def _as_catalog_refusal(refusal: BillingRuleError, default_br_ref: str) -> errors.BizError:
    """A service-layer rule refusal, as the ONE catalog exception G9 allows.

    `BillingRuleError` is deliberately not a catalog exception (see
    `apps/billing/exceptions.py`): a stage running inside a batch over
    thousands of accounts is not answering a request, and a catalog code
    carries an HTTP status. This layer IS answering a request, so it is where
    the translation belongs, and it is the only place in the module that knows
    what HTTP is.

    ONE code for all of them — 422 BIZ-COMPLETENESS — and that uniformity is
    deliberate. Every refusal that reaches here has the same shape: *this
    cannot be done as asked, here is the rule and here is the sentence a clerk
    can act on.* Picking among the nine BIZ codes per refusal would be this
    layer INTERPRETING rules it does not own, and the interpretation would
    drift from the module that raised them. The refusal's own sentence travels
    in `params.detail` and its BR-ID in `br_ref`, which is what BR-AUD-018's
    attempt row records.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.

    ⚠ **ONE EXCEPTION, AND IT IS NOT A LOOSENING — `DEF-2720`.** A refusal may
    NAME its own catalogue key and hand over figures as params, and when it does
    that key is used instead of the generic one. This is the opposite of
    rendering `detail`: the sentence is still composed in the catalogue, in
    eleven languages, and what crosses the seam is numbers.

    It exists because the bill-run size ceiling is the one refusal whose entire
    content is three facts a clerk must act on — *this run covers 41,000
    accounts, this system bills at most 25,000 in one pass, split the cycle* —
    and what they read instead was *"This billing run can't go ahead as
    asked."* Uniformity is right for a refusal that says *not as asked* and
    wrong for one that says *here is the number*.

    `detail` is unchanged and still travels: the audit attempt row and the log
    get the full sentence either way.

    ⚠ **THE TWO BRANCHES BELOW ARE NOT WORTH COLLAPSING, AND THIS LANE PROVED
    IT BY COLLAPSING THEM FIRST.** The tidy form is one `return` with
    `message_key=named_key or "billing.run.refused"`. It works, `tsc`-equivalent
    checks pass, every test stayed green — **and `G32` and `G33` both stopped
    seeing `billing.run.refused` at all**, because they read `message_key=` as an
    AST keyword and a literal buried in a boolean expression is not one. The
    count fell from 851 keys to 851 with a different member: the module's single
    most-used refusal key silently left the set two gates walk, which is the
    check-that-cannot-fail this repo keeps paying for. Measured, not feared —
    `G32`'s own `raised_keys()` was asked before and after. Keep the literal in
    the keyword position.
    """
    named_key = getattr(refusal, "message_key", None)
    named_params = getattr(refusal, "params", None) or {}
    br_ref = getattr(refusal, "br_ref", None) or default_br_ref
    if named_key is not None:
        return errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=br_ref,
            message_key=named_key,
            params={**named_params, "detail": str(refusal)},
        )
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key="billing.run.refused",
        params={"detail": str(refusal)},
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Reads & Billing runs — Executive View
def invoices(request: Any) -> Response:
    """S30 All bills (11b §2.8 · US-BIL-025), and the S21 Bills tab scoped by
    `f.account_id` — one endpoint, because a per-tab read model would be a
    second place for BR-BIL-063's draft rule and the past-due posture to drift.

    Pagination is mandatory on every list (11b G5) and its sizes are ratified
    at 50/100/200/500/1000, default 50 (A11 Addendum r2). The page is taken in
    the DATABASE: only the rows on screen are serialized.

    The header roll-up rides alongside the DRF envelope exactly as
    `GET /accounts` answers, and its money members are null — see
    `selectors.invoices_rollup`.
    """
    require_tenant(request)
    params = selectors.list_params(request.query_params)
    paginator = StandardPagination()
    page = paginator.paginate_queryset(selectors.invoice_list_queryset(params), request)
    response = paginator.get_paginated_response(
        [selectors.invoice_row(invoice) for invoice in (page or [])]
    )
    response.data["rollup"] = selectors.invoices_rollup()
    return response


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def invoice_item(request: Any, invoice_id: str) -> Response:
    """S30 bill detail (11b §2.8 · US-BIL-026) — READ ONLY, by law.

    An unknown id, a malformed id and another tenant's id are ONE answer
    (HR-1 / 11b G4): the response body is byte-identical, so existence cannot
    be probed. US-BIL-026 TC-6 requires exactly that, and the screen's own
    message names all three possibilities rather than picking one.
    """
    require_tenant(request)
    return Response(selectors.invoice_detail(invoice_id))


# ══════════════════════════════════════════════════════════════════════════
# S31 THE BILL RUN (US-BIL-001..005) — 11b §2.8, plus the §2.8b bodies
#
# The wizard shipped on 2026-08-11 calling five `/billing/runs…` paths against
# a 404 and DERIVING the absence from the response, so each panel stops
# apologising the day its route lands. Four landed that day. The fifth — and the
# RELEASE GATE the wizard's step 5 needed and no row had ever contracted — land
# here on 2026-08-15, which is DEF-116.
#
# ⚠ **WHAT THIS BLOCK USED TO SAY, AND WHY IT IS WRONG** (hard-won law 1 — the
# correction is the point, not the deletion). It read: *"POST /billing/runs/
# {id}/issue — NOT SERVED, and not stubbed. `issue.issue_run` needs three things
# this layer cannot honestly supply."* Every one of the three has since become
# supplyable, and the wizard sat at READY TO BILL 0 for four days on a paragraph
# that was true when it was written:
#
#   (a) **the template pin.** *"BR-BIL-025's category-default assignment has no
#       table (r10 #4)"* — it does now (`template_models.py`, migration 0018,
#       2026-08-15) and `templates_service.resolve_for` implements that rule's
#       own resolution order. `_template_pin_for` asks for it, and a tenant with
#       no template is refused with the rule's sentence rather than issued
#       against an invented uuid, which is what the original objection was
#       actually protecting.
#   (b) **the event time.** *"BR-TEN-043 makes event time the CALLER's, and
#       there is no clock in this money path."* Both true, and neither is a
#       reason not to ACCEPT one: `issued_at` and `confirmed_at` are required
#       body fields, offset-bearing, refused when naive. Not reading a clock and
#       not having a time are different problems.
#   (c) **the authorised release row.** `POST /billing/runs/{id}/release` writes
#       it, from the same five confirmations the S31 gate already collects, and
#       `POST .../issue` refuses without it (US-BIL-005 TC-14).
#
# ⚠ **AND A THIRD BRICK NOBODY HAD NAMED, MOUNTED 2026-08-16.** With release
# and issue both mounted the wizard STILL could not bill anyone: **nothing in
# the product ever called `runs.calculate_run`**, so every run reached the gate
# with zero drafts and `POST .../release` refused, correctly — *"run … has no
# bills to release … an authorisation of nothing would be a signature against a
# blank page"*, measured on a booted stack. The engine had shipped on
# 2026-08-11 with tests and a place in `pipeline.PUBLIC_ENTRY_POINTS`, and no
# caller outside its own tests. `POST /billing/runs/{id}/calculate` is that
# caller. Hard-won law 2, one phase earlier than anybody was looking.
#
# ⚠ **TWO OF THE THREE ABSENCES BELOW ARE CLOSED (CR-051, 2026-08-30) AND THE
# REASONS GIVEN FOR THEM HAVE EXPIRED. Corrected rather than left standing —
# hard-won law 1, whose second half is the one that bites here: a comment
# claiming an ABSENCE outlives the absence, and every reader after it plans
# around a gap that closed.**
#
#   · ~~a GET for the BREAK list (BR-BIL-053)~~ — **SERVED.** The reason given
#     was exactly right at the time: *"`runs.CalculatedRun.breaks` exists only
#     in memory … Serving one would mean CALCULATING inside a read, which writes
#     drafts."* Migration 0026 gives the breaks a table (`bill_run_breaks`),
#     `runs.record_break` writes a row per account as the pass finds it, and
#     `GET /billing/runs/{id}/breaks` READS rows and writes nothing. The clerk
#     who navigates away, logs out or hands over at a shift change comes back to
#     the same list, and two people looking at it see the same rows.
#   · ~~`GET /billing/runs/{id}`~~ — **MOUNTED.** The reason given was *"the poll
#     exists to watch a BACKGROUND batch, and there is no background batch
#     (TD-17). A status endpoint whose value can never change while the caller
#     watches is a promise of asynchrony this deployment does not keep."*
#     **BOTH HALVES HAVE EXPIRED.** There IS a background batch —
#     `apps/billing/run_jobs.py` registers three job kinds and billing is the
#     fifth module to use machinery that has been running since CR-017 landed
#     the worker on 2026-08-19 — and the route was never only a poll: it is the
#     only way to RE-OPEN a finished run at all, which has nothing to do with
#     asynchrony. `selectors.run_detail_dict` serves the phase, the scope, the
#     decisions and the counts.
#
# STILL NOT SERVED, for a stated reason rather than an oversight:
#   · the phase-4 summary as a GET, and the release RECORD as a screen —
#     OQ-112 is CLOSED (PO 2026-08-11, option B: *"B An export only"*): the
#     authorisation record gets an EXPORT and deliberately no screen. Mounting
#     a GET for it would implement the option the PO declined. The summary IS
#     computed and IS stored by `POST .../release`, which is the write the
#     ruling never spoke about; it is returned in that response because it is
#     what the caller just authorised, not as a panel they can re-open.
# ══════════════════════════════════════════════════════════════════════════
class BillRunsAccess(AnyTenantRole):
    """A4 `reads_billing_runs` — READ for any tenant role, WRITE for Admin or
    Clerk. The same split `RoutesConfigAccess` makes in `apps/metering/api.py`,
    and made here for the same reason it was made there.

    ⚠ **THE TWO VERBS ON THIS PATH HAVE DIFFERENT AUDIENCES.** `POST` creates a
    run and has been `AdminOrClerk` since it landed (A4 gives the Executive
    **View** on Reads & Billing runs, not Full). The `GET` added by CR-029
    RC-W4b is SET-07D's run history and is a read like every other read in this
    file, so it takes `AnyTenantRole` — an Executive who cannot open a cycle's
    Runs tab has been given a View they cannot use.

    Django maps one URL to one view, so the split cannot be two
    `@permission_classes`; it is a class rather than an `if request.method`
    inside the view because a permission rule belongs where it can be read,
    cited and tested, and `test_w4b_8` asserts both halves apart.

    ⚠ **NOT THE WHOLE GUARD.** `runs.create_run` keeps its own service-layer
    posture; this is the refusal at the door with the right HTTP status
    (BR-SHL-025 is server-enforced, never a disabled button).
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return super().has_permission(request, view)
        return AdminOrClerk().has_permission(request, view)


def _page_envelope(request: Any, result: dict[str, Any]) -> dict[str, Any]:
    """A selector's page dict → **the four keys this product puts on the wire**.

    ⚠ **THIS IS A BOUNDARY AND IT RENAMES EVERYTHING, WHICH IS WHY THREE SCREENS
    ONCE SHIPPED BLANK** (`DEF-WRK-4119`, `DEF-AST-4120`, 2026-09-05). In goes
    `{rows, page, per, total, pages}`; out goes `{count, next, previous,
    results}`. A front-end type written from `selectors.py` — the right file for
    the ROW shape and the wrong one for the REPLY — reads `data.rows`, gets
    `undefined`, and renders its own *no results* state with total confidence.
    `07-frontend/src/api/paginated.ts` is the ONE description of these four names
    and asserts them at runtime; read it before typing a client for this route.

    It builds a FRESH dict, so **any extra fact a view serves must be spread
    back in** — `{**_page_envelope(request, result), "tiles": …}` — which is the
    line `asset_work_orders` did not write and lost `maintenance_index` over.

    ⚠ **IT IS THE THIRD HAND-BUILT COPY OF THIS FUNCTION** (`apps/work/api.py`
    and `apps/runbooks/api.py` hold the other two, byte-for-byte the same
    arithmetic). It is not shared because `core.pagination` owns DRF's paginator
    for the views that page a QUERYSET, and these three page inside their
    selectors; the honest fix is one helper there, and moving two other modules'
    boundary function is not this lane's to do. Named rather than left for
    somebody to discover a fourth time.
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


@api_view(["GET", "POST"])
@permission_classes([BillRunsAccess])  # A4 reads_billing_runs: Executive is VIEW
def bill_runs(request: Any) -> Response:
    """`GET` — SET-07D's **Runs** tab (CR-029 RC-W4b, B17 §4). `POST` — S31
    step 1's exit (11b §2.8 · US-BIL-001): ONE `bill_runs` row in draft.

    ── THE GET ───────────────────────────────────────────────────────────────
    **THE BLUEPRINT'S SCREEN 27, §07 Past billing runs (p145–p146).** Seven
    drawn columns — RUN · CYCLE · PERIOD · BILLS · VALUE · RUN BY · STATUS —
    newest first, with four tiles above them and a real pager below. The cycle
    detail's own Runs tab reads the same route with `f.cycle_id`.

    **PARAMS:** BR-SHL-011's grammar. `q` searches run number, cycle and person
    (the placeholder's own three things); `f.cycle_id`, `f.status` and `f.year`
    are the three chips the toolbar draws; `page` and `per` page it, `per`
    clamping to 50/100/200/500/1000. There is NO `sort`: p146 draws no sort
    affordance on any heading, and a control nobody drew is a control invented
    (B14 rule 37 — build the shape, not the figures).

    ⚠ **IT USED TO TAKE A CLAMPED `limit` WITH NO TOTAL AND THE REASON GIVEN
    HAS EXPIRED (amended 2026-09-15).** The old note argued *"a run history grows
    at the TOP, so page 2 of it is not a stable read … there is no pager on the
    Runs tab to drive one either"*. The second half was true of the CYCLE tab
    and is untrue of this screen, which draws *"Showing 1–34 of 34"* with a
    rows-per-page control; the first half is answered by a TOTAL order rather
    than waved away. **`NFR-3` is why it matters and `NFR-5` is why a ceiling of
    200 could not stay**: correct at a 3,000-connection utility, silently
    truncating at a 40,000-account one.

    **THE ENVELOPE IS `{count, next, previous, results}` PLUS `tiles`.** That is
    the four names `07-frontend/src/api/paginated.ts` declares, and the extra key
    is spread back in by hand because `_page_envelope` returns a fresh dict.
    ⚠ **IT ANSWERED `{"runs": [...]}` UNTIL 2026-09-15** — one caller,
    `getBillRuns` in `endpoints.ts`, and it moved in the same commit.

    ⚠ **TWO THINGS THIS DOCSTRING TOLD SESSIONS WERE IMPOSSIBLE, AND BOTH WERE
    FALSE WHEN THEY WERE READ (`DEF-BIL-5353`, the corrections are below in the
    lifecycle block with their dates):** `run_no` is populated and real runs
    carry `RUN-0001` upward, and the rule that kept MONEY off this row is about
    another module's creation screens. The VALUE column is served: Σ of the run's
    locked bills as the stored decimal string beside its `CHAR(3)` currency.

    ⚠ **AND `status` NOW MOVES** (`BR-BIL-1045`, `DEF-BIL-5352`). It read
    `"draft"` on every finished run this product had ever made — including one
    that had issued 1,251 bills — because both its writers wrote at creation.
    `runs.record_run_outcome` is the one writer now; `selectors.bill_runs_page`
    and `runs.py`'s status block carry the whole argument.

    This endpoint was skipped by RC-W3b on purpose — `apps/billing/api.py` was
    a live sibling lane's file at the time (hard-won law 11) — and the cycle
    detail shipped a stated absence naming it, which is the only reason a
    missing endpoint stayed visible for a day instead of for a release.

    ── THE POST ──────────────────────────────────────────────────────────────

    ⚠ **AMENDED 2026-09-30 (bulk bill run redesign, plan A1/B1/B3/B4).** The
    POST is now `run_scope_api.create`: every Scope refusal and warning at once
    (`field_errors` + `params.warnings`), run name and template REQUIRED, and
    `scope_services` no longer read — the PO removed the services filter. The
    paragraphs below about `bill_date` and `due_days` still hold.

    201 with the id inline. 11b marks this row STALE against B12 r1's
    `202 + job_id` law — that law is about ASYNC operations, and this is one
    insert with nothing queued behind it, so `job_id` is served null rather
    than pointing at a poll that would answer nothing. `billRunIdOf()` reads
    `id ?? run_id` and refuses to guess when neither arrives; `id` is the one
    served. **11b §2.8b records exactly this**, so the next lane reads what was
    served rather than re-deriving it.

    `bill_date` IS ACCEPTED AND STORED (BR-BIL-070 — PO ruling 2026-08-11
    closing OQ-122, option A: *"A Store what they type and use it"*). It lands
    on `bill_runs.bill_date` and becomes the run's SERVICE date, so a run whose
    clerk typed 3 Aug over a cycle dated 1 Aug prices at 3 Aug. Omitting it, or
    sending null or "", records that nobody typed one and the cycle's date is
    used — the behaviour every run had before the ruling.

    This docstring previously read *"`bill_date` IS ACCEPTED AND NOT STORED …
    OQ-122 carries the divergence to the PO"*. The OQ is closed and the claim
    is now false, so it is rewritten rather than left standing (hard-won law 1).

    `due_days` IS ACCEPTED AND STORED TOO (CR-029 D9, PO 2026-08-23: *"when we
    configure Cycle we are provideing default values; mostly it wil remain as it
    is but user can over ride them during billing"*). Worked, and it is the
    figure the ruling was confirmed on: cycle 06-A bills 1 July with 21
    due-days, so an ordinary run falls due **22 July**; a run created with
    `due_days: 14` falls due **15 July**, and the cycle still says 21 for the
    next run. `0` is lawful and means due on the bill date.
    """
    require_tenant(request)
    if request.method == "GET":
        params = parse_list_params(
            request.query_params,
            allowed_filters=selectors.BILL_RUN_LIST_FILTERS,
        )
        page = selectors.bill_runs_page(
            q=params.q,
            cycle_id=params.filters.get("cycle_id") or None,
            status=params.filters.get("status") or None,
            year=params.filters.get("year") or None,
            page=params.page,
            per=params.per,
            bill_type=params.filters.get("bill_type") or None,
        )
        return Response(
            {
                **_page_envelope(request, page),
                # The four tiles, spread back in because `_page_envelope`
                # returns a fresh dict and discards everything else — the exact
                # line `asset_work_orders` did not write (`DEF-AST-4120`).
                "tiles": selectors.bill_run_tiles(year=params.filters.get("year") or None),
            }
        )
    # ── THE POST: the bulk run's Scope step (plan A1, PO 2026-09-30) ─────────
    # Every refusal and warning on row 43 of `14-bulk-bill-run-changes.md` is
    # checked in ONE pass before anything is written, run name and template are
    # required, and `scope_services` is no longer read (B3). It lives in
    # `run_scope_api.create` so this busy file carries one line of it.
    from apps.billing import run_scope_api

    return run_scope_api.create(request)


#: What the background half of the findings pass does NOT do (CR-051 task 9).
FINDINGS_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "the_findings_job_records_counts_not_the_case_lists",
        "br_ref": "BR-BIL-051 · OQ-843",
        # ⚠ NO ROUTE, NO ID, NO RULE REFERENCE IN THIS STRING — CR-016 and G28.
        # It is a SERVED value, and the first draft named two HTTP paths and an
        # open question in it; the gate caught it and the provenance moved up
        # here, where it belongs. The routes it used to name are the background
        # findings POST and the findings GET, and the open question is OQ-843.
        "detail": "asking for the findings pass in the background runs it on the server and "
        "records what it COUNTED — how many accounts, how many are ready, how many are "
        "blocked and how many are waiting on a decision — against the run, so somebody who "
        "closed the tab can be told the pass finished without waiting for a second one. The "
        "case tables themselves are not kept: opening them works the pass out again from the "
        "meters, plans and accounts as they stand right now, so anyone who fixes a plan and "
        "comes back sees the fix rather than the world as it was when they started.",
    },
)


@api_view(["GET", "POST"])
@permission_classes([BillRunsAccess])  # GET is any tenant role; POST is Admin or Clerk
def run_findings(request: Any, run_id: str) -> Response:
    """S31.2 "Check what we found" (11b §2.8 · US-BIL-002) — phase 1, READ ONLY.

    `runs.prepare_run` writes NOTHING — not a draft, not an exclusion, not a
    status change — which is what makes this safe to serve on a GET a clerk may
    refresh. The body is `runs.PreparedRun` field for field; see
    `selectors.findings_dict` for why it is not paginated.

    ── THE POST (CR-051 task 9), AND WHY THE VERB CHANGED ────────────────────
    The GET *"re-runs the whole prepare pass over every account in the cycle, on
    a GET a clerk can refresh"* — measured and named by CR-051. `POST` with
    `background: true` hands that pass to a worker and answers 202 with the poll
    address, so the clerk is not held. **It is a POST rather than a GET with a
    parameter because it CREATES A JOB RECORD**, which is a write, and a GET
    that writes is the thing `selectors.py` is careful never to do.

    **WHAT IT LEAVES BEHIND IS COUNTS, NOT A CACHE, AND THE DIFFERENCE IS
    STATED ON EVERY RESPONSE** (`FINDINGS_UNAVAILABLE`). The GET is unchanged
    and still recomputes. Snapshotting the case lists is `OQ-843`.

    A POST with no `background: true` runs the pass inline and answers the same
    body the GET does — the honest shape when nothing would run a job.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    if request.method == "POST":
        payload = _payload(request)
        if _wants_background(payload):
            ready, reason = run_jobs.would_run()
            if ready:
                record = run_jobs.enqueue_findings(run, actor_user_id=_actor_id(request))
                return Response(
                    {
                        **core_jobs.accepted(record),
                        "bill_run_id": str(run.pk),
                        "background": True,
                        "unavailable": [dict(entry) for entry in FINDINGS_UNAVAILABLE],
                    },
                    status=202,
                )
            # ⛔ ABOVE THE BAR THIS REFUSES — see the same block on
            # `run_calculate` for why, and CR-105-BRC03 for the blueprint
            # sentence. **This is the screen p050 is actually drawing**: it is
            # the pre-bill CHECK a clerk presses *Prepare* for, and its own
            # panel says *"Today the clerk presses Prepare and waits on one
            # request … the request wall is about 60 seconds."*
            try:
                run_jobs.refuse_if_no_worker(run, reason=reason)
            except BillingRuleError as refusal:
                raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal
            logger.warning(
                "findings for run %s asked for background and fell back to INLINE: "
                "nothing would have run it (%s)",
                run.pk,
                reason,
            )
        try:
            return Response(
                {
                    **selectors.findings_dict(run),
                    "background": False,
                    "unavailable": [dict(entry) for entry in FINDINGS_UNAVAILABLE],
                }
            )
        except BillingRuleError as refusal:
            raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal
    try:
        body = selectors.findings_dict(run)
        # B14 rule 16 / NFR-3 — one named list at a time, paged, when the caller
        # asks for one. Absent, the whole body is served exactly as before; see
        # `_findings_page` for why the page is not the default yet.
        which = request.query_params.get("list")
        if which in FINDINGS_LISTS:
            return Response(_findings_page(request, body, which))
        return Response(body)
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal


#: The four lists `GET /billing/runs/{id}/findings` serves. Naming one pages
#: THAT list; naming none serves the whole body exactly as it always has.
FINDINGS_LISTS: tuple[str, ...] = ("ready", "blocked", "decisions", "silent")


def _findings_page(request: Any, body: dict[str, Any], which: str) -> dict[str, Any]:
    """One named findings list, paged — B14 rule 16's footer, served.

    ⚠ **OPT-IN, AND THAT IS DELIBERATE RATHER THAN TIMID.** The unpaginated body
    is what every count on the Check screen is computed from today, so making a
    page the DEFAULT would turn `ready.length` into a page size and the screen
    would confidently report fifty accounts in a run of ten thousand — the
    exact failure the endpoint's own docstring warns about. The counts now have
    their own address; the day the screen reads them from there, paging becomes
    the default and this parameter goes away.
    """
    rows = list(body.get(which) or ())
    per = clamp_page_size(request.query_params.get("per"))
    try:
        page = int(str(request.query_params.get("page")))
    except (TypeError, ValueError):
        page = 1
    # BR-SHL-011 "never error": a garbage or out-of-range page clamps.
    last = max((len(rows) + per - 1) // per, 1)
    page = min(max(page, 1), last)
    start = (page - 1) * per
    return {
        **{key: value for key, value in body.items() if key not in FINDINGS_LISTS},
        "list": which,
        "results": rows[start : start + per],
        "count": len(rows),
        "page": page,
        "per": per,
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # the same readership as the findings it counts
def run_finding_counts(request: Any, run_id: str) -> Response:
    """Screen 17's band strip and KPI strip — THE NUMBERS, WITHOUT THE ROWS.

    ⚠ **WHY IT IS ITS OWN ADDRESS.** Every chip on the Check screen is `.length`
    of an array the browser was sent, over a findings read that is unpaginated
    BY DECLARED DESIGN — because its lists are the denominator the chips count.
    That is one argument holding up both halves, and this endpoint is what takes
    it apart: once the counts arrive as counts, the rows are free to page. At
    10,000 accounts the old shape put ten thousand account rows on the wire on
    every refresh to draw twenty-six numbers.

    ⛔ **IT IS NOT A CACHE AND MAY NOT BECOME ONE.** `OQ-843` is CLOSED on the
    PO's ruling that the pass is dynamic — a clerk who fixes a plan and comes
    back must see the fix. This recomputes, like the findings read beside it.
    What it saves is the wire and the browser's arithmetic.

    **`as_of` IS REQUIRED.** The waiting-time bands are measured against a day,
    and *today* belongs to the tenant rather than to this process (BR-TEN-043 /
    gate G6). A queue whose ages came from the server's clock ages by a day the
    moment somebody opens it from another timezone.

    **`age_bands_from` IS AN UNANSWERED QUESTION WEARING A PARAMETER.** An
    account held across cycles has two candidate cycles whose bands could
    govern it — the one it was held from, and the one being run now — and which
    is right has not been ruled. Sending neither is the honest default: those
    accounts are counted on their own and kept out of the three age tags rather
    than banded on a guess.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        return Response(
            selectors.finding_counts(
                run,
                as_of=_query_date(request, "as_of"),
                age_bands_from=request.query_params.get("age_bands_from"),
            )
        )
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive View on Reads & Billing runs
def run_scope(request: Any) -> Response:
    """Screen 16's `SCOPE` group and its `WHAT THIS COVERS` card. READ ONLY.

    **EVERY FIGURE IS A COUNT — no money and no forecast**, which is the
    drawing's own note and a cost rule before it is a taste rule: resolving a
    scope FOR REAL costs the measured 137 ms per account, so a card that showed
    what a scope was worth would pay for the whole run to draw its header.

    ⚠ **IT RESOLVES A SCOPE; IT DOES NOT SCOPE A RUN, AND IT SAYS SO.** A run's
    idempotency key is cycle + period and carries no scope, so a narrowed run
    consumes the key for the whole period and everything it left out is refused
    as a duplicate — with no exclusion row written, so those accounts never
    reach the held queue and nothing ever bills them. `committable` is therefore
    FALSE for every narrowed scope, with the limit stated in the clerk's own
    words. A scope chooser shipped over that key is a revenue hole with a
    dropdown on it; this is the half of it that can ship today.

    Parameters: `cycle_id` (required), `scope` (one of the drawn kinds,
    defaulting to the whole cycle), `scope_id` (repeatable) and `f.service`
    (repeatable — the services a run would be narrowed to).
    """
    require_tenant(request)
    try:
        services = request.query_params.getlist("f.service") or None
        scope_ids = request.query_params.getlist("scope_id")
    except AttributeError:  # pragma: no cover - a plain dict in a unit test
        services = None
        scope_ids = []
    try:
        return Response(
            selectors.scope_resolution(
                cycle_id=request.query_params.get("cycle_id"),
                kind=request.query_params.get("scope") or selectors.SCOPE_CYCLE,
                scope_ids=scope_ids,
                scope_services=services,
            )
        )
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: the same readership as the scope it sits beside
def run_case_defaults(request: Any) -> Response:
    """Screen 16's `DEFAULTS` group — WHAT TO OFFER AND WHAT IT OPENS ON. READ ONLY.

    The blueprint calls this group *"the single biggest error-reducer in this
    redraw"* (p047): three decisions a clerk makes ONCE instead of hundreds of
    times per account. To draw it a screen needs three things it cannot know —
    which cases carry a standing answer, which choices each offers, and what the
    tenant's own setting opens each control on.

    ⚠ **IT EXISTS SO THAT NO LIST IS TYPED INTO A SCREEN.** The PO's instruction
    of 2026-09-14 is *"no hardcoding"*, and `resolve_case_defaults` obeys it by
    spelling no literal at all — it validates against `decisions.CHOICES_BY_CASE`
    and fills from `settings_seam.run_case_defaults()`. A browser that carried
    its own copy of those words would drift off them the day either changed, and
    the failure mode is a control that submits a choice the server then refuses.
    `decisions.CHOICES_BY_CASE` says exactly this in its own docstring about
    S31.3, and this is the same argument one screen earlier.

    ⚠ **`holds` IS SERVED PER CHOICE BECAUSE THE DRAWING REQUIRES IT**: *"every
    option states whether it bills or holds"* (p032, p036 — *"Two of them hold
    and produce no bill, and a clerk cannot be expected to know which"*). It is
    read from `decisions.HOLDING_CHOICES`, the same set `_is_held` reads, so the
    word on the option and the behaviour at prepare time cannot disagree.

    ⚠ **NO WORDS FOR A CLERK ARE SERVED HERE, DELIBERATELY.** The codes are the
    contract; the catalogues render them. A sentence composed in this module
    would be a twelfth locale nobody translates (G15/G18), and the two absences
    this product distinguishes — *no such choice* and *no catalogue entry* —
    would collapse into one.

    ⚠ **THE THREE CASES COME FROM `RUN_CASE_DEFAULT_KEYS`, NOT FROM THIS FILE.**
    That mapping is the one place a settings key is spelled, which is why
    `runs.py` never spells one; naming the three here would be the second copy
    the whole arrangement exists to avoid.
    """
    require_tenant(request)
    from apps.billing import decisions, settings_seam

    try:
        opens_on = settings_seam.run_case_defaults()
    except BillingConfigError as refusal:
        # The tenant's settings could not be read. A default substituted here
        # would be a second copy of a finance-visible figure (BR-BIL-1040), so
        # the group is REFUSED with its reason rather than drawn on a guess.
        raise _as_catalog_refusal(
            BillingRuleError(str(refusal), br_ref="BR-BIL-1040"), "BR-BIL-1040"
        ) from refusal
    return Response(
        {
            "cases": [
                {
                    "case": case_kind,
                    "opens_on": choice,
                    "choices": [
                        {
                            "code": offered,
                            "holds": (case_kind, offered) in decisions.HOLDING_CHOICES,
                        }
                        for offered in decisions.CHOICES_BY_CASE.get(case_kind, ())
                    ],
                }
                for case_kind, choice in sorted(opens_on.items())
            ]
        }
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # the same readership as the findings it sits beside
def run_pricing_shadow(request: Any, run_id: str) -> Response:
    """S31.2's PRICING-SHADOW panel — step 3 of the R1–R7 cutover. READ ONLY.

    Runs the ruled pricing chain beside the live path over this run's ready
    accounts and reports every place the two answer differently. **It prices
    nothing and writes nothing**: the decision log's own table gives step 3
    "nothing" under *what changes on a bill*, and this route is not on any path
    a bill travels.

    ⚠ **IT IS A SECOND REQUEST, NOT A MEMBER OF `findings`, ON PURPOSE.** The
    findings body is the stage a clerk cannot bill without; the comparison is
    advisory and is allowed to be empty, slow or unhappy without taking the
    billable stage down with it. `shadow_report` says why at length.

    The body always carries `attempted` beside `disagreed` — *"read the third
    and fourth numbers together or they lie: 0 disagreed is also what perfect
    agreement looks like"* — and always carries `not_attempted` with
    `blocked_by_reason`, so an operator can tell agreement from a question
    nobody could ask.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        prepared = selectors.prepared_for(run)
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal
    return Response(shadow_report.report_for_prepared(prepared))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def run_exceptions(request: Any, run_id: str) -> Response:
    """S31.3's case tables (11b §2.8 · US-BIL-003) — phase 1, READ ONLY.

    Same prepare pass as the findings, asked a different question: which
    accounts are waiting on a human, what may be chosen for each, and what has
    been chosen already.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        return Response(selectors.exceptions_dict(run))
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_exception_resolve(request: Any, run_id: str, case_id: str) -> Response:
    """One recorded staff decision, or one bulk action (11b §2.8 · US-BIL-003).

    *"All the decisions are made on screen and recorded"* — recorded is the
    operative word, and the row carries who made it. `case_ids` in the body is
    BR-BIL-060's bulk: N rows sharing ONE `bulk_action_id`, minted by the
    SERVER because only the server can share an id across rows.

    `amount` + `unit` are accepted because BR-BIL-015's *estimate* disposition
    is a QUANTITY a clerk supplies and `record_decision` refuses one without
    its unit (CLAUDE.md rule 3). **No screen sends them yet** — the shipped
    `BillRunResolveBody` carries `choice`, `reason` and `case_ids` only — so
    choosing *estimate* over HTTP refuses today with that rule's own sentence.
    REPORTED to the S31 lane rather than worked around here.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    try:
        bulk_action_id, rows = decisions.resolve_cases(
            bill_run=run,
            case_id=case_id,
            choice=payload.get("choice"),
            reason=payload.get("reason"),
            case_ids=payload.get("case_ids"),
            amount=_decimal_field(payload, "amount"),
            unit=payload.get("unit"),
            decided_by=_actor_id(request),
        )
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal
    # ── `DEF-BIL-5271`(a) · THE DECISION NOW REACHES THE MONEY ───────────────
    # Recording was the whole of this endpoint until 2026-09-14, and the drafts
    # it decided about kept their pre-decision figures: a clerk could bulk-decide
    # 44 estimated accounts under one `bulk_action_id` and every bill still said
    # what it said before. `runs.reprice_accounts` re-runs phases 1 and 2 for
    # exactly the accounts these rows name — the same engine, the same worker
    # and the same progress channel as a full calculate, narrowed.
    #
    # ⚠ **IT IS SKIPPED WHERE THERE IS NOTHING TO RE-PRICE, AND THAT IS A
    # MEASUREMENT RATHER THAN AN OPTIMISATION.** A decision taken BEFORE the
    # calculate pass — which is the ordinary S31.3 flow, step 3 before step 4 —
    # has no draft to replace, and re-pricing there would draft bills the clerk
    # has not asked for yet and would make step 3 a committing action. The
    # question asked is *does this run hold a draft for any of these accounts*.
    #
    # ⚠ **AND IT IS NOT OPTIONAL WHEN IT DOES RUN.** `runs.refuse_stale_drafts`
    # holds the run out of phase 4 while any draft predates a decision about its
    # account (BR-BIL-053, extended), so a re-price that silently failed here
    # surfaces at the gate instead of on a customer's bill.
    repriced: dict[str, Any] = {"accounts": 0, "drafts": 0, "background": False, "job_id": None}
    scope = decisions.accounts_touched(rows)
    if scope and runs.has_drafts_for(run, scope):
        ready, _reason = run_jobs.would_run()
        if _wants_background(payload) and ready:
            # The SAME choice `run_calculate` gives, and for the same reason: a
            # bulk decision over a large cohort is a long re-price and a clerk
            # may close the tab. Inline otherwise — never queued into a void,
            # because an accepted job that re-prices nobody, for ever, is worse
            # than the visible wait it replaced.
            record = run_jobs.enqueue_reprice(run, scope, actor_user_id=_actor_id(request))
            repriced = {
                "accounts": len(scope),
                "drafts": 0,
                "background": True,
                "job_id": str(record.get("id")),
            }
        else:
            try:
                calculated = runs.reprice_accounts(
                    bill_run=run, account_ids=scope, bill_type=run.bill_type
                )
            except BillingRuleError as refusal:
                raise _as_catalog_refusal(refusal, "BR-BIL-053") from refusal
            repriced = {
                "accounts": len(scope),
                "drafts": calculated.drafted_count,
                "background": False,
                "job_id": None,
            }
    return Response(
        {
            "bulk_action_id": None if bulk_action_id is None else str(bulk_action_id),
            "decision_ids": [str(row.pk) for row in rows],
            # WHAT THE DECISION DID TO THE MONEY, on the same response that
            # records it — so a screen whose drawn sub-line reads *"updates as
            # you decide"* has something true to render.
            "repriced": repriced,
        },
        status=201,
    )


#: What `POST /billing/runs/{id}/calculate` cannot do, served on every response.
#:
#: ⚠ **BOTH ENTRIES THAT USED TO BE HERE ARE GONE, NOT EDITED, BECAUSE BOTH
#: STATEMENTS BECAME FALSE ON 2026-08-30 (CR-051).** They read
#: `calculate_is_not_a_background_batch` (*"There is no worker on this
#: deployment (TD-17) … a 202 would be a promise of asynchrony this deployment
#: does not keep"*) and `the_break_list_is_returned_and_not_stored` (*"there is
#: no `GET /billing/runs/{id}/breaks`"*). A worker has run since CR-017 landed
#: it on 2026-08-19, and `bill_run_breaks` (migration 0026) is a table. Leaving
#: either standing would be hard-won law 1 in its most expensive form — a
#: SERVED sentence telling every caller a capability does not exist.
CALCULATE_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "background_is_asked_for_and_not_measured",
        "br_ref": "BR-BIL-051",
        "detail": "phase 2 runs in a BE-07 worker when the caller sends `background: true`, "
        "and INLINE otherwise. The default is inline because there is no timing figure for a "
        "bill run of any size anywhere in this product yet — the premises import set its own "
        "5,000-row bar from a measured 50,000-row file, and the equivalent measurement for a "
        "run is owed. Choosing a threshold without it would be inventing a number. Inline "
        "still holds the caller until every ready account has been drafted or broken.",
    },
    {
        "code": "no_worker_means_inline_not_refused",
        "br_ref": "BR-BIL-051",
        "detail": "if `background: true` is asked for on a deployment where nothing would run "
        "the job, the run executes INLINE and this response says so on `background: false` "
        "with a 201 rather than a 202. It is never queued into a void: an accepted job that "
        "bills nobody, for ever, is worse than the visible wait it replaced. The premises "
        "import REFUSES in the same situation, and the difference is deliberate — 50,000 "
        "rows inline exceeds the request timeout, so inline is not an option there.",
    },
)


def _wants_background(payload: dict[str, Any]) -> bool:
    """Did the caller ask for this verb to run in a worker? (CR-051 tasks 8/9.)

    ⚠ **LITERAL `true` AND NOTHING ELSE.** `"yes"`, `1` and a missing key all
    mean *no*, the same posture `_confirmations_from` takes for the release
    gate: a truthy coercion is how *"the caller asked"* becomes
    indistinguishable from *"the caller sent something"*, and here it decides
    whether a person is held at a screen or told to come back.

    **WHY A FLAG AND NOT A ROW BAR.** `apps/metering/import_runs.async_row_bar`
    decides by MEASURED row count. There is no equivalent measurement for a bill
    run anywhere in this repository — CR-051 says so and makes measuring it task
    21 — and picking a threshold without one would be inventing a figure. Until
    that measurement exists the caller asks, the default is unchanged, and every
    existing caller behaves exactly as it did.
    """
    return payload.get("background") is True


def _accept_background(record: dict[str, Any], run: Any) -> Response:
    """The 202 for an enqueued run verb: the job id, the poll address, the run.

    `core.jobs.accepted` is the WHOLE of B12 r1's accept contract — `job_id` and
    `status_url` — and nothing is added to it beyond the run id the caller
    already holds, because status truth lives at the poll endpoint and a second
    copy here is a second thing to go stale. The poll address is the platform
    path the framework already serves (`/api/jobs/{id}`); this route neither
    builds it nor knows its shape.
    """
    return Response(
        {
            **core_jobs.accepted(record),
            "bill_run_id": str(run.pk),
            "background": True,
            "unavailable": [dict(entry) for entry in CALCULATE_UNAVAILABLE],
        },
        status=202,
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive View on Reads & Billing runs
def run_item(request: Any, run_id: str) -> Response:
    """`GET /billing/runs/{id}` — ONE run: its phase, scope, decisions, counts.

    CR-051 task 1, and the block above the run views records why it was absent
    and why that reason expired. READ ONLY: five grouped queries over rows that
    already exist, and no prepare pass — which is exactly what `GET .../findings`
    cannot claim, because that one re-runs the whole of phase 1 on every refresh.

    **`phase` IS DERIVED FROM EVIDENCE AND `status` IS THE STORED COLUMN.** Both
    are served, and they answer different questions: `phase` is how far this run
    got through the WIZARD (draft · calculated · authorised · issued), `status`
    is the word screen 27's STATUS column shows a clerk (`BR-BIL-1045`).

    ⚠ **THIS PARAGRAPH SAID `status` IS WRITTEN `"draft"` AT CREATION AND NEVER
    MOVES, AND UNTIL 2026-09-15 IT WAS TRUE (`DEF-BIL-5352`).** It moves now —
    `runs.record_run_outcome` advances it the instant the issue pass returns, so
    the reason `phase` had to exist at all is half gone. `phase` STAYS: a run may
    be authorised with nothing issued, and no status word says that. The stored
    column is served beside the derived one rather than hidden, which is what
    made the defect findable in the first place.

    No money of any kind (BR-MET-078 as hardened by CR-029).
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(selectors.run_detail_dict(run))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # the same readership as the run it belongs to
def run_read_lock(request: Any, run_id: str) -> Response:
    """`GET /billing/runs/{id}/read-lock` — the Sent card's *"Meter reads:
    Locked"* (DEF-BIL-8685), on its own read since `DEF-BIL-8809`.

    It rode `GET /billing/runs/{id}` and was ~1.1 s of that read's 1.2 s on a
    sent 40,008-bill run, so every screen of the bulk run page waited for a
    row only the Sent card draws. Null until the run is released with nothing
    left to send. No money."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(selectors.run_read_lock_dict(run))


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: the gate is read by whoever signs it
def run_summary(request: Any, run_id: str) -> Response:
    """`GET /billing/runs/{id}/summary` — PHASE 4's panel (US-BIL-005 · DEF-2853).

    ⚠ **`release.summary_for` HAS COMPUTED EVERY FIGURE ON THIS PANEL SINCE
    2026-08-11 AND HAD NO CALLER BUT `POST .../release`, WHICH STORES IT AND
    NEVER SERVES IT BACK.** So S31 steps 4 and 5 drew *"Customers in this run —
    Not worked out"*, *"Usage, per service — Not worked out"* and *"Amount — Not
    worked out"* over a complete, tested implementation, and a clerk was asked to
    sign a release against figures the product would not show them. Hard-won law
    2, one function over from DEF-116's own two routes. `EP-BIL-01`'s field map
    had written the gap down in prose — *"still no endpoint and no screen"* — and
    nothing reads prose for truth.

    **THE FOUR FIGURES ARE THE PO's OWN WORDS** (2026-08-11): *"show the billing
    summary in how many accounts, how many bills generated, how much consumption
    and how much bill amount and various categories"*. Consumption carries its
    explicit unit and is never summed across units (rule 3); the amount carries
    its currency (rule 2).

    **IT RECALCULATES ON EVERY CALL AND THAT IS THE RULING, NOT AN OVERSIGHT.**
    PO 2026-08-11, option B, put in plain English with its worked figure: approve
    480 bills at $52,847.19, void two next week, and the screen must read 478.
    So this route reads the run's CURRENT bills and reads `bill_run_releases`
    never. `POST .../release` answers the other question — what was authorised —
    and after that ruling the stored row is the ONLY answer to it.

    **READ ONLY, AND MONEY-BEARING, WHICH IS WHY IT IS NOT A FIELD ON
    `GET /billing/runs/{id}`.** That route is five grouped counts with no money
    at all (BR-MET-078 as hardened by CR-029) and it is POLLED while a batch
    runs. This one sums bills, walks every correction chain (BR-BIL-064) and
    reaches the customers seam for mandate coverage; it is read once, at the
    gate. Folding it in would put a money aggregation on a poll.

    A refusal from the summary is a REFUSAL, not an empty panel: a run holding a
    `corrected` bill that nothing replaces cannot say what the customer owes now,
    and both figures it could reach are wrong (`current_position_bills` argues
    it at length). It surfaces under BR-BIL-056 rather than being flattened to
    zero.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        return Response(selectors.run_summary_dict(release.summary_for(run)))
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-056") from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # the same readership as `/summary`
def run_totals(request: Any, run_id: str) -> Response:
    """`GET /billing/runs/{id}/totals` — `/summary`'s headline alone: bills,
    amount net of credit notes, currency (`DEF-BIL-8809`).

    The bulk run page draws exactly these from the panel (the Sent card's
    total, the Send step's bill count) and was asking for the whole of it —
    consumption, three category axes, coverage, the waived list — ~1.1 s at
    40,008 bills, on the read the Sent card waits for. Same functions as
    `/summary` (`release.totals_for`), live on every call, the same refusals
    under the same rule."""
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        return Response(selectors.run_totals_dict(release.totals_for(run)))
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-056") from refusal


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # the same readership as the run it belongs to
def run_breaks(request: Any, run_id: str) -> Response:
    """`GET /billing/runs/{id}/breaks` — BR-BIL-053's list, and it SURVIVES now.

    CR-051 tasks 5/6. Until migration 0026 the breaks lived only in
    `runs.CalculatedRun.breaks`, so this endpoint could not exist without
    calculating inside a read. It now reads `bill_run_breaks` and writes
    nothing: a refresh, a logout and a shift change all leave the list intact,
    and two clerks working it see the same rows and the same resolutions because
    the list is the server's rather than each browser's.

    OUTSTANDING BY DEFAULT — that is the work list, and BR-BIL-053's own word.
    `?f.resolved=all` adds the ones a later pass drafted, for the supervisor's
    question rather than the clerk's.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    return Response(
        selectors.run_breaks_dict(
            run,
            include_resolved=request.query_params.get("f.resolved") == "all",
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_break_retry(request: Any, run_id: str, account_id: str) -> Response:
    """BR-BIL-053's FIRST way out — *"retry immediately by fixing the issue"*.

    ⚠ **`runs.retry_account` HAS EXISTED, COMPLETE AND TESTED, SINCE 2026-08-11
    AND HAD NO HTTP CALLER** (DEF-2856, and `DEF-2557` filed the frontend half
    of the same absence). So the break panel drew its Retry control DISABLED
    carrying *"Trying one customer again is not something this screen can do
    yet"* — accurate, and it left a clerk one option for a single missing read:
    re-run the whole cycle. Hard-won law 2, and neither suite could see it,
    because the backend tests call the function directly and the frontend test
    asserts the disabled control.

    **ONE ACCOUNT, STAGES 1–6, AND NOTHING ELSE IS TOUCHED.** The other drafts
    are not recomputed and no other break is closed. On success the account
    joins the draft set and its break row closes as `drafted` — the same value a
    whole-run pass writes, because it is the same fact.

    **A RETRY THAT STILL FAILS IS A REFUSAL, NOT A 201.** Nothing was fixed, the
    account still cannot be billed, and the break row is left exactly as it was:
    `retry_account` closes it only after the draft commits. Answering success
    over an account that still has no read would move the discovery to the gate.

    **IT IS NOT A RE-PRICE.** BR-BIL-023 is unchanged and unchangeable here: a
    computed amount is never typed over, and this route accepts no amount, no
    quantity and no line. What it accepts is the request to try again after a
    human fixed what the reason named.

    **THE CLERK'S RECORDED DECISIONS ARE FOLDED IN FIRST**, exactly as
    `run_calculate` does it — an account whose missing read was answered on
    S31.3 must retry on that answer, or the retry fails for the reason the
    clerk has already dealt with. It is a POST, which is where a write belongs;
    `selectors.py` records why a GET must never reach `apply_decisions`.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        prepared = selectors.prepared_for(run)
        prepared = decisions.apply_decisions(prepared, bill_run=run)
        invoice = runs.retry_account(prepared, str(account_id), bill_run=run)
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-053") from refusal
    if invoice is None:
        # ⚠ **THE RETRY SUCCEEDED AND THERE IS NO BILL (`BR-BIL-1024`).** The
        # account priced no lines, so no document was produced — which is a
        # correct outcome and not a failure: the break row is closed either way
        # (`retry_account` closes it after the call), and the account is quiet
        # rather than broken. Answered with the same envelope and NULL ids
        # rather than a 500 on `invoice.pk`, and `resolution` says which of the
        # two happened so the screen never has to infer it from a null.
        return Response(
            {
                "bill_run_id": str(run.pk),
                "account_id": str(account_id),
                "invoice_id": None,
                "invoice_no": None,
                "resolution": runs.RUN_NOTHING_TO_BILL,
            },
            status=200,
        )
    return Response(
        {
            "bill_run_id": str(run.pk),
            "account_id": str(account_id),
            "invoice_id": str(invoice.pk),
            # BR-BIL-063: the draft carries its number from creation, so the
            # screen can name the bill it just produced.
            "invoice_no": invoice.invoice_no,
            "resolution": models.BREAK_RESOLUTION_DRAFTED,
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_break_hold(request: Any, run_id: str, account_id: str) -> Response:
    """BR-BIL-053's SECOND way out — *"or mark for later"*.

    The account joins the Pending-billing queue and waits for a catch-up
    sub-run; the rest of the run issues (BR-BIL-055 — *"a break never blocks the
    run"*). It writes the `bill_run_exclusions` row that IS that queue, and it
    goes through `pending.mark_break_for_later` rather than
    `runs.mark_for_later` for the reason that wrapper exists: the reason code
    has to carry the STAGE (BR-BIL-040), so the queue can tell *"we never
    calculated this"* from *"we calculated it and it broke"*, and a call site
    that composed its own code would produce a row whose origin is `unknown`.

    **THE STAGE COMES FROM THE STORED BREAK ROW, NEVER FROM THE CALLER.** A
    client-supplied stage would be a fact about the failure invented by
    something that did not witness it. A request naming an account with no
    outstanding break is refused rather than queued on a guess.

    **IDEMPOTENT (hard rule 6)** on (run, account) through the table's own
    unique constraint, so a double-click marks once and answers success — a
    replay is not an error.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    row = (
        models.BillRunBreak.objects.filter(
            tenant_id=request.tenant_id, bill_run=run, account_id=account_id
        )
        .order_by("-created_at")
        .first()
    )
    if row is None:
        raise _as_catalog_refusal(
            BillingRuleError(
                "this account has no break on this run, so there is nothing to mark for "
                "later. Holding it would write a queue row naming a failure that was "
                "never recorded — a phase-1 hold is a different door and writes a "
                "different reason code (BR-BIL-015).",
                br_ref="BR-BIL-053",
            ),
            "BR-BIL-053",
        )
    try:
        exclusion = pending.mark_break_for_later(
            bill_run=run,
            account_id=str(account_id),
            stage=row.stage or "",
            reason=row.reason,
            detail=payload.get("detail") or row.detail or "",
            excluded_by=_actor_id(request),
        )
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-053") from refusal
    return Response(
        {
            "bill_run_id": str(run.pk),
            "account_id": str(account_id),
            "exclusion_id": str(exclusion.pk),
            "reason_code": exclusion.reason_code,
            "resolution": models.BREAK_RESOLUTION_HELD,
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_calculate(request: Any, run_id: str) -> Response:
    """S31 step 4's "Work out the bills" — PHASE 2 (US-BIL-004 · BR-BIL-051/052).

    ⚠ **THIS ROUTE WAS THE THIRD BRICK IN DEF-116's WALL, AND IT WAS THE ONE
    NOBODY HAD NAMED.** The defect reported *"the wizard drives to a 201 draft
    run and then reports READY TO BILL 0, Draft bills 0"* and its prevention
    column asked for the release and issue routes. Both were mounted on
    2026-08-15 — and the run STILL could not issue, because **nothing in the
    product ever called `runs.calculate_run`.** Measured on a booted stack the
    day after: `POST .../release` answered *"run … has no bills to release, so
    there is no amount and no currency to record … an authorisation of nothing
    would be a signature against a blank page"*, which is the correct refusal
    over an empty run. The engine was built on 2026-08-11, tested, listed in
    `pipeline.PUBLIC_ENTRY_POINTS`, and had **no caller outside its own tests**
    — hard-won law 2 again, one phase earlier than anybody was looking.

    **WHAT ONE CALL DOES:** phase 1's prepare pass (which writes nothing), then
    one DRAFT per ready account, each in its own transaction. **A break never
    stops the run** (BR-BIL-055): the account that failed comes back named, with
    the STAGE it stopped at, and every other draft is untouched.

    **NOTHING MONEY-BEARING EXISTS WHEN IT RETURNS** (J24 step 4, BR-BIL-004): a
    draft carries no `issued_at`, no stamped GL account, no journal line and no
    delivery row. That is why this is a route a clerk may click twice: it is the
    last phase before the gate, and the gate is where money starts.

    **IDEMPOTENT (hard rule 6) BY CONSTRUCTION, NOT BY A FLAG.** Stage 6
    REPLACES an account's draft for this run rather than adding a second
    (BR-BIL-023), and stages 1–5 are pure — so a re-run converges on the same
    drafts and a killed pass resumes without recomputing what it already wrote
    (BR-BIL-052). The guarantee lives in the WRITE, which is the only place it
    cannot rot.

    NO EVENT TIME IS TAKEN, and that is not an oversight: the service date is
    the bill date the clerk typed on step 1 (BR-BIL-070) and comes off the run
    row through `runs.effective_bill_date`. There is no clock in this file (G6).

    **`background: true` HANDS THE PASS TO A WORKER AND ANSWERS 202** (CR-051
    task 8 · BR-BIL-051, whose background half has been unsatisfied since
    2026-08-11). The body is the job id and the poll address `/api/jobs/{id}`
    the framework already serves; the clerk may close the tab. Absent, this runs
    inline exactly as it always has — see `_wants_background` for why the choice
    is the caller's rather than a row threshold, and `CALCULATE_UNAVAILABLE` for
    what is served about it on every response.

    A SECOND CLICK IS ONE JOB, NOT TWO PASSES. The enqueue carries the scope key
    `billing:calculate:<run id>`, so a re-enqueue while that job is still active
    returns THE EXISTING RECORD (NFR-16). That decides what a second CLICK does;
    BR-BIL-023's draft replacement decides what a second PASS does, and neither
    substitutes for the other.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    if _wants_background(payload):
        ready, reason = run_jobs.would_run()
        if ready:
            record = run_jobs.enqueue_calculate(run, actor_user_id=_actor_id(request))
            return _accept_background(record, run)
        # ⛔ ABOVE THE BAR THIS REFUSES; BELOW IT, IT FALLS BACK TO INLINE
        # (CR-105-BRC03 · blueprint p050: *"Refuse rather than run inline above
        # the bar — a deployment with no worker runs the check inline today and
        # the request dies long before its own `ran inline` answer can be
        # read."*). It was the second half alone until 2026-09-14, and on a
        # 25,000-account run that meant a dead connection at 60 seconds over a
        # server still working 57 minutes later, with the `background: false`
        # member that would have explained it in a body nobody received.
        #
        # The `reason` is LOGGED and never shown either way: it is a short
        # technical phrase for a support line, and CR-016 keeps internal
        # references off a utility's screen. Below the bar what the clerk gets
        # is the finished result, late; above it, a sentence they can act on.
        try:
            run_jobs.refuse_if_no_worker(run, reason=reason)
        except BillingRuleError as refusal:
            raise _as_catalog_refusal(refusal, "BR-BIL-051") from refusal
        logger.warning(
            "calculate for run %s asked for background and fell back to INLINE: "
            "nothing would have run it (%s)",
            run.pk,
            reason,
        )
    try:
        # CR-051 task 30 — the ceiling, checked before anything is drafted. It
        # is INSIDE the try so the existing handler two blocks down turns it
        # into a catalog refusal like every other rule refusal on this route.
        # The background branch above is covered by `enqueue_calculate` itself.
        run_jobs.refuse_if_oversized(run)
        prepared = selectors.prepared_for(run)
        # ⚠ **THE CLERK'S DECISIONS ARE FOLDED IN HERE, AND NOTHING HAD EVER
        # CALLED THIS EITHER.** `decisions.apply_decisions` has existed since
        # 2026-08-11 with its own tests and no production caller, so a run whose
        # clerk had answered every missing-read case still broke at
        # measure-consumption with *"still has no usable read and no decision"*
        # — the decision was recorded, audited, visible on S31.3, and never
        # read. Measured in a browser on 2026-08-16. This is the SECOND
        # built-not-wired in one phase, and the reason both hid is the same: a
        # phase with no route has no place for its own steps to be called from.
        #
        # It goes HERE and not in `prepared_for`, deliberately: applying
        # decisions WRITES (a held account gains a `bill_run_exclusions` row —
        # the pending queue's first door), and `selectors.py` records that a
        # GET must never reach it. A POST is where a write belongs.
        prepared = decisions.apply_decisions(prepared, bill_run=run)
        calculated = runs.calculate_run(prepared, bill_run=run)
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-051") from refusal
    return Response(
        {
            **selectors.calculated_run_dict(calculated),
            # FALSE, and it is a fact rather than a default: either the caller
            # did not ask, or it asked and nothing would have run the job. The
            # `unavailable` entries name both cases.
            "background": False,
            "unavailable": [dict(entry) for entry in CALCULATE_UNAVAILABLE],
        },
        status=201,
    )


def _datetime_field(payload: dict[str, Any], name: str, *, required: bool = True) -> Any:
    """An ISO-8601 INSTANT the CALLER named — never a clock read (BR-TEN-043).

    Gate G6 bans a wall clock from every money path in this repository, and the
    reason is not tidiness: `issued_at` lands on an immutable invoice and
    `confirmed_at` is the moment somebody authorised money leaving. A retried
    submit must record ONE moment rather than two, and only the caller knows
    which one it is.

    A NAIVE timestamp is REFUSED rather than assumed UTC. "2026-07-03T09:41"
    means a different instant in Houston than in Chennai, and a bill run whose
    stamped moment depended on where the browser was is BR-TEN-020's whole
    warning. The client sends `new Date().toISOString()`, which is always
    offset-bearing.
    """
    raw = payload.get(name)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        if not required:
            return None
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.run.event_time_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.event_time_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.event_time_naive",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        )
    return moment


def _confirmations_from(payload: dict[str, Any]) -> release.Confirmations:
    """BR-BIL-058's five facts, off the wire, as five values.

    The key names are `release.Confirmations`' own field names and the S31
    gate's `GATE_FACTS` ids — `compliance`, `email_mandate`, `sms_mandate`,
    `autopay_mandate`, `final` — which are already the same five strings on both
    sides. One vocabulary, so a rename goes red in a test rather than silently
    recording four confirmations as five.

    ANYTHING THAT IS NOT LITERAL `true` IS NOT A CONFIRMATION. `"yes"`, `1` and
    a missing key are all *not confirmed*, because this is the record of a human
    saying go before money leaves and a truthy coercion is how "the box was
    ticked" becomes indistinguishable from "the client sent something". The
    service refuses and NAMES each untaken one (US-BIL-005 TC-10).
    """
    given = payload.get("confirmations")
    if not isinstance(given, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.confirmations_required",
            field_errors=[{"field": "confirmations", "code": errors.VAL_FORMAT}],
        )
    return release.Confirmations(
        compliance=given.get("compliance") is True,
        email_mandate=given.get("email_mandate") is True,
        sms_mandate=given.get("sms_mandate") is True,
        autopay_mandate=given.get("autopay_mandate") is True,
        final=given.get("final") is True,
    )


def _template_pin_for(payload: dict[str, Any], *, run: Any = None) -> tuple[Any, int, bool]:
    """BR-BIL-026's pin for this run — RESOLVED, never invented.

    ⚠ **THIS IS THE BLOCKER THAT KEPT THE ISSUE ROUTE UNMOUNTED FOR FOUR DAYS,
    AND IT IS CLOSED.** The block above the run views used to say issue *"needs
    three things this layer cannot honestly supply"*, the first being the
    template pin: *"BR-BIL-025's category-default assignment has no table (r10
    #4) — there is nothing to derive a pin from and inventing one puts a bill in
    the world that can never say what rendered it."* The table landed on
    2026-08-15 (`apps/billing/template_models.py`, migration 0018) and
    `templates_service.resolve_for` implements BR-BIL-025's own resolution
    order. So the pin is ASKED FOR, and the sentence above is corrected rather
    than left standing (hard-won law 1).

    THREE SOURCES, IN THIS ORDER:

      * ⚠ **THE RUN'S OWN PIN — `bill_runs.template_id`, chosen at Scope.**
        `DEF-BIL-5302`, added 2026-09-14. PO ruling of the same day: *"in this
        step 1 scope - you will ahve to also decide on billing template"*. The
        column was written by `create_run` through `validated_template_pin` and
        **had no reader anywhere**, so a clerk picked a template at Scope, we
        stored it, and issue then re-resolved from whatever the request happened
        to carry. The pinned layout and the printed layout could differ with
        nothing raising. **A decision made at Scope that issue does not read is
        a decision that did not happen.**
      * an EXPLICIT `template_id` + `template_version` in the body. Both or
        neither — half a pin is not a pin, and a caller that sent an id with no
        version would otherwise get the resolved version silently attached to
        their id.
      * otherwise the tenant's own resolution: `resolve_for(consumer_category=
        None)`, which is BR-BIL-025's FALLBACK template and its published
        version. A tenant with no template at all is REFUSED with that rule's
        own sentence rather than issued against an invented uuid.

    ⚠ **WHY THE RUN OUTRANKS THE BODY, STATED SO IT IS NOT "SIMPLIFIED" BACK.**
    The body's pair is a statement about THIS REQUEST; the run's pin is a
    statement about THIS RUN, made at Scope, stored, and shown to the clerk who
    signed the release. When the two disagree the stored one is the one a human
    actually chose and the one the gate re-checked
    (`runs.refuse_unresolvable_template`), so it wins. The body's pair is NOT
    deleted — it is the answer for a caller that has no run — and the tenant's
    BR-BIL-025 fallback stays last, exactly where it was.

    ⚠ **THE RUN PINS A TEMPLATE AND NEVER A VERSION**, which is
    `validated_template_pin`'s own deliberate choice: *"Pinning a version here
    would be stale by Send on any tenant that publishes in between."* So the
    PUBLISHED version is resolved here, at issue, off the pinned template. A pin
    whose template has since lost its published version never reaches this
    function — the gate refuses the release first — and if it somehow does, the
    tenant fallback below is NOT silently substituted: that would print a layout
    nobody chose, which is this defect over again.

    ⚠ **THE PARAGRAPH THAT STOOD HERE IS NO LONGER TRUE AND IS REPLACED RATHER
    THAN EDITED (hard-won law 1, CR-052 W3 task 12).** It read: *"ONE PIN FOR THE
    WHOLE RUN, AND BR-BIL-025 WANTS ONE PER ACCOUNT. `issue.issue_run` takes a
    single pin and applies it to every bill in the pass … the per-account
    resolution belongs inside the issue loop, which is a 🔒 money path and
    another change."* **That change is made.** `issue.issue_run` now resolves
    BR-BIL-025's chain per draft — account override → category default → tenant
    fallback — and counts which bills answered for themselves.

    **SO WHAT THIS FUNCTION RETURNS IS THE RUN's PIN PLUS WHETHER A HUMAN TYPED
    IT**, and the third value is the whole of the difference. An EXPLICIT pin is
    a statement about THIS RUN and governs every bill in it; a RESOLVED one is
    the tenant's fallback, which is the right answer for an account whose own
    chain cannot be read and the wrong one to force on an account that has a
    category template. Returning a bare pair would make the two indistinguishable
    by the time they reach the issue loop.
    """
    pinned = None if run is None else getattr(run, "template_id", None)
    if pinned is not None:
        # Imported at CALL time, the idiom `runs.validated_template_pin` and
        # `issue._pin_for_account` both use: `template_models` imports billing's
        # `models`, which is a closed loop at module scope.
        from apps.billing import template_models

        template = template_models.BillTemplate.objects.filter(
            tenant_id=run.tenant_id, pk=pinned
        ).first()
        version = None if template is None else templates_service.published_version(template)
        if version is None:
            # The gate (`runs.refuse_unresolvable_template`) refuses this before
            # a clerk can sign, so reaching here means the template went between
            # sign-off and Send. REFUSED rather than fallen back on: substituting
            # the tenant default would print a layout nobody chose, which is the
            # defect this branch exists to close.
            raise BillingRuleError(
                "the bill template this run was scoped to can no longer be printed, so "
                "the run cannot issue on it (BR-BIL-026). Nothing is resolved in its "
                "place: a bill printed on a layout nobody picked is the choice made at "
                "Scope not having happened.",
                br_ref="BR-BIL-026",
            )
        # EXPLICIT, and for the same reason a typed pair is: a clerk chose this
        # for the WHOLE RUN, so it governs every bill in it rather than being
        # overridden by BR-BIL-025's per-account chain.
        return template.pk, version.version_no, True
    given_id = payload.get("template_id")
    given_version = payload.get("template_version")
    if given_id is not None or given_version is not None:
        if given_id is None or given_version is None:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="billing.run.template_pin_partial",
                field_errors=[
                    {"field": "template_id", "code": errors.VAL_FORMAT},
                    {"field": "template_version", "code": errors.VAL_FORMAT},
                ],
            )
        try:
            # EXPLICIT — the caller typed both halves. `True` is what stops the
            # per-account chain from quietly overriding what a clerk asked for.
            return given_id, int(given_version), True
        except (TypeError, ValueError) as problem:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="billing.run.template_pin_partial",
                field_errors=[{"field": "template_version", "code": errors.VAL_FORMAT}],
            ) from problem
    template, version = templates_service.resolve_for(consumer_category=None)
    # RESOLVED, not typed: BR-BIL-025's FALLBACK. Every account in the run then
    # resolves its own chain and uses this only when it cannot be read.
    return template.pk, version.version_no, False


#: What the two phase-4/5 routes CANNOT do, served on every response. The
#: `ISSUE_UNAVAILABLE` / `PENDING_UNAVAILABLE` discipline: a caller must not have
#: to infer an absence from a silence (hard-won law 1).
RELEASE_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # ⚠ **THE ENTRY THAT STOOD HERE — `one_template_pin_for_the_whole_run` —
    # IS WITHDRAWN (CR-052 W3 task 13, 2026-08-31), NOT EDITED.** It said the pin
    # was *"resolved ONCE for the run … and every bill in the pass is pinned to
    # it"* and that *"the per-account resolution belongs inside the issue loop and
    # is owed"*. It is no longer owed: `issue.issue_run` resolves BR-BIL-025's
    # chain for every draft — account override → category default → tenant
    # fallback — through `templates_service.resolve_for`, and reports
    # `template_resolved_per_account` beside `template_pinned_by_run` on the
    # result. A stated absence that outlives the absence is a lie the product
    # tells about itself (hard-won law 1), which is why it is deleted in the same
    # commit the capability lands and not a release later.
    {
        "code": "the_presented_summary_is_the_servers_own",
        "br_ref": "BR-BIL-056 · BR-BIL-058",
        "detail": "`bill_run_releases.summary` records what was SHOWN at sign-off, and this "
        "route stores the summary the SERVER computes at the moment of confirmation rather "
        "than a payload echoed back by the screen. That is deliberate and it is the safer "
        "half of `release.authorise_release`'s own warning: a client-supplied payload would "
        "be recorded as having been shown. What it does NOT close is drift — the figures "
        "the clerk read a minute earlier may have moved, and nothing binds the two. Closing "
        "that needs a signed render token, which does not exist, and a 'the figures moved' "
        "refusal would be a rule the PO never gave.",
    },
    # ⚠ **THE ENTRY THAT STOOD HERE — `release_is_not_a_background_batch` — SAID
    #: *"There is no worker on this deployment (TD-17), so `POST .../issue` runs
    #: the whole issue pass INLINE … a 202 would be a promise of asynchrony this
    #: deployment does not keep"*. IT IS FALSE AS OF 2026-08-30 AND IS REPLACED
    #: RATHER THAN EDITED (hard-won law 1).** A worker has run since CR-017
    #: landed it on 2026-08-19, and `background: true` now issues in one.
    {
        "code": "issue_runs_in_the_background_when_asked",
        "br_ref": "BR-BIL-051",
        "detail": "`POST .../issue` with `background: true` hands the issue pass to a worker "
        "and answers 202 with the poll address, so the gate can return the clerk to the "
        "bills list without holding them while 1,122 bills issue. Absent, it runs INLINE and "
        "answers 201 with the finished result, exactly as it always has. The default is "
        "inline because no timing figure for an issue pass of any size exists in this "
        "product yet, and choosing a threshold without one would be inventing a number. If "
        "background is asked for where nothing would run the job, the pass runs inline and "
        "the response says so rather than queueing into a void.",
    },
)


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_release(request: Any, run_id: str) -> Response:
    """S31 step 5's sign-off — the RELEASE GATE (11b §2.8 · US-BIL-005, phase 4).

    🔒 HUMAN-REVIEW-PENDING — this is the door money goes through. It writes the
    `bill_run_releases` row that `issue_run` requires and nothing else can
    forge; row in 12-governance/09-human-review-ledger.md.

    BR-BIL-058, the PO's own words: *"take final confirm from user, compliance
    confirmation, emails, text mandates, auto pay mandates and then release the
    bills"*. FIVE separately recorded facts, not one tick, because *"a release
    that went out without the compliance check is a different event from one
    that did"*. The service refuses while any is untaken and NAMES every one of
    them (US-BIL-005 TC-10).

    **IT ISSUES NOTHING.** This is the last moment at which nothing has been
    billed, and that is the point of separating it from `POST .../issue`: the
    gate is the record of authorisation, and the release is the act. A crash
    between the two leaves exactly the state TC-13 describes — a row with
    `released_at` NULL, authorised but not released — which is a resumable
    position rather than a re-authorisation.

    **IDEMPOTENT (hard rule 6).** A run that already has an AUTHORISED BUT
    UNRELEASED row answers **200 `created: false`** with that row instead of
    writing a second: TC-13 requires that a resume *"does NOT ask for
    authorisation a second time"*, and a double-clicked Confirm is the same
    shape at one second's distance. A run whose release is already RELEASED is
    a different case entirely and gets a new row — `release_run`'s own docstring
    says a second authorised release (a catch-up sub-run, a resumed batch) is a
    SECOND row with its own confirmations.

    `confirmed_at` is REQUIRED and is the caller's (BR-TEN-043 / G6). There is
    no clock in this path.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    confirmations = _confirmations_from(payload)
    confirmed_at = _datetime_field(payload, "confirmed_at")

    pending_row = release.pending_releases(run).first()
    if pending_row is not None:
        return Response(
            {
                **selectors.release_dict(pending_row, created=False),
                "unavailable": [dict(entry) for entry in RELEASE_UNAVAILABLE],
            },
            status=200,
        )
    try:
        summary = release.summary_for(run)
        row = release.authorise_release(
            bill_run=run,
            summary=summary,
            confirmations=confirmations,
            confirmed_by=_actor_id(request),
            confirmed_at=confirmed_at,
            actor=getattr(request, "user", None),
        )
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-058") from refusal
    return Response(
        {
            **selectors.release_dict(row, created=True),
            "unavailable": [dict(entry) for entry in RELEASE_UNAVAILABLE],
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_issue(request: Any, run_id: str) -> Response:
    """S31 step 6's "Send them out" — PHASE 5 (11b §2.8 · US-BIL-005 · BR-BIL-051).

    🔒 HUMAN-REVIEW-PENDING — this is the transition INTO financial
    immutability. After this call an issued bill cannot be un-issued, only
    corrected by a new row (hard rule 4); row in
    12-governance/09-human-review-ledger.md.

    ⚠ **THIS ROUTE WAS ABSENT FOR FOUR DAYS AND THE PARAGRAPH THAT EXPLAINED WHY
    IS NOW WRONG IN ALL THREE OF ITS CLAUSES** (DEF-116 — *"the bill-run wizard
    cannot issue"*). It said issue needed three things this layer could not
    honestly supply. (a) The **template pin** — BR-BIL-025's table now exists
    and `_template_pin_for` asks for it. (b) The **event time** — `issued_at` is
    a required body field, which is what BR-TEN-043 asks for: the CALLER names
    the moment, and refusing to invent one was never a reason not to accept one.
    (c) The **authorised release row** — `POST .../release` writes it, and this
    route refuses without it. Each is corrected here rather than left standing
    (hard-won law 1).

    IT CALLS `release.release_run`, which is phase 5 whole: the issue pass, and
    then `released_at` stamped on the authorisation row IF the pass returns.
    The order is the design — stamping first would turn a crash mid-issue into a
    run that claims to have gone out.

    **WHAT ONE CALL DOES, per bill and in one transaction each** (issue's own
    docstring is the long form): the number the DRAFT already carries is
    verified, the due date is derived, BR-BIL-035's arrears are stamped, the
    document is rendered as the BR-BIL-033 precondition, every line's GL account
    is stamped and frozen, the status moves, `audit_log` is written, the
    balanced posting handoff is emitted to the ledger's sole writer, and the
    delivery rows are queued. **Queueing is not sending** and `ran: true` on a
    handoff never means a customer received a bill.

    **A BREAK NEVER BLOCKS THE RUN** (BR-BIL-055). 499 issue and one comes back
    named in `issued.broken`; there is no batch rollback and there never will be.

    **IDEMPOTENT (hard rule 6), at two levels and both of them matter.** The
    inner one is structural: `issue_run` selects the run's REMAINING DRAFTS, so
    a second pass finds nothing and issues nothing (US-BIL-005 TC-6) — the
    guarantee lives in the SELECTION, which cannot rot, rather than in a flag.
    The outer one is this route: a run whose release is already stamped
    `released_at` answers **200 `created: false`** with that release rather than
    a refusal, because a double-clicked Send is a replay and not an error — the
    shape `POST /accounts/{id}/payments` already gives a replayed payment
    (11b §2.9b).

    `issued_at` is REQUIRED and is the caller's. `released_at` may be sent
    separately and DEFAULTS to `issued_at`, because they are one business
    moment: the clerk pressed Send once, the bills carry that instant, and the
    release completed at it. The default is a stated reading of one event, never
    a clock read — there is no clock in this file (G6).
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    payload = _payload(request)
    issued_at = _datetime_field(payload, "issued_at")
    released_at = _datetime_field(payload, "released_at", required=False) or issued_at
    dispatch_not_before = _datetime_field(payload, "dispatch_not_before", required=False)
    invoice_ids = payload.get("invoice_ids")
    if invoice_ids is not None and not isinstance(invoice_ids, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.run.invoice_ids_invalid",
            field_errors=[{"field": "invoice_ids", "code": errors.VAL_FORMAT}],
        )

    release_row = release.pending_releases(run).first()
    if release_row is None:
        # Either the gate was never recorded — the forged-POST case US-BIL-005
        # TC-14 names — or it was recorded AND completed, which is a replay.
        # The two are told apart here rather than by the caller, because they
        # deserve opposite answers: a refusal, and an idempotent success.
        done = release.completed_releases(run).first()
        if done is not None:
            return Response(
                {
                    **selectors.release_dict(done, created=False),
                    "unavailable": [dict(entry) for entry in RELEASE_UNAVAILABLE],
                },
                status=200,
            )
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-058",
            message_key="billing.run.no_authorised_release",
            params={
                "detail": (
                    f"run {run.pk} has no authorised release, so nothing may be issued. The "
                    "gate is five separately recorded facts — compliance, email mandate, "
                    "text mandate, autopay mandate, and the confirmation itself — and it is "
                    "the last moment at which nothing has been billed (BR-BIL-058). Record "
                    "it with POST /billing/runs/{id}/release first."
                )
            },
        )

    # ── CR-051 task 9 — the issue pass to a worker, when the caller asks ──────
    # ⚠ **THE GATE IS CHECKED BEFORE THE ENQUEUE AND THAT ORDER IS THE POINT.**
    # US-BIL-005 TC-14's forged POST straight to issue is refused above, at the
    # door, on the REQUEST — so a job record for an unauthorised run can never
    # be created, and the worker never has to be the place that decision lives.
    # The template pin is resolved here for the same reason: it needs the
    # tenant's own resolution and a body a worker does not have.
    if _wants_background(payload):
        ready, reason = run_jobs.would_run()
        if ready:
            # DEF-BIL-8710 — Send pressed again over a Send whose worker DIED
            # hands it back to a worker. Before, the scope key folded the press
            # into the stuck record and answered 202 with it, and nothing ever
            # moved it again. A Send still being worked is left alone (the
            # press folds into it below, as before).
            stuck = send_batches.send_job_for(run)
            if stuck is not None and run_jobs.job_is_abandoned(stuck["id"]):
                try:
                    record, outcome = run_jobs.resume_job(run, stuck["id"])
                except BillingRuleError as refusal:
                    raise _as_catalog_refusal(refusal, "BR-BIL-051") from refusal
                return Response(
                    {
                        **core_jobs.accepted(record),
                        "bill_run_id": str(run.pk),
                        "release_id": str(release_row.pk),
                        "background": True,
                        "resumed": outcome == core_jobs.REDISPATCHED,
                        "unavailable": [dict(entry) for entry in RELEASE_UNAVAILABLE],
                    },
                    status=202,
                )
            try:
                template_id, template_version, pin_explicit = _template_pin_for(
                    payload, run=run
                )
            except BillingRuleError as refusal:
                raise _as_catalog_refusal(refusal, "BR-BIL-026") from refusal
            record = run_jobs.enqueue_issue(
                run,
                issued_at=issued_at,
                released_at=released_at,
                template_id=template_id,
                template_version=template_version,
                invoice_ids=invoice_ids,
                dispatch_not_before=dispatch_not_before,
                actor_user_id=_actor_id(request),
                # CR-052 task 12 — the worker cannot re-derive whether a human
                # typed this pin, because the request body is gone by then.
                template_pin_explicit=pin_explicit,
            )
            return Response(
                {
                    **core_jobs.accepted(record),
                    "bill_run_id": str(run.pk),
                    "release_id": str(release_row.pk),
                    "background": True,
                    "unavailable": [dict(entry) for entry in RELEASE_UNAVAILABLE],
                },
                status=202,
            )
        logger.warning(
            "issue for run %s asked for background and fell back to INLINE: "
            "nothing would have run it (%s)",
            run.pk,
            reason,
        )

    try:
        template_id, template_version, pin_explicit = _template_pin_for(payload, run=run)
        outcome = release.release_run(
            bill_run=run,
            release_row=release_row,
            released_at=released_at,
            issued_at=issued_at,
            template_id=template_id,
            template_version=template_version,
            invoice_ids=None if invoice_ids is None else tuple(invoice_ids),
            actor=getattr(request, "user", None),
            dispatch_not_before=dispatch_not_before,
            # CR-052 task 12 — BR-BIL-025 resolves per ACCOUNT inside the issue
            # loop unless a clerk typed a pin for this whole run.
            template_pin_explicit=pin_explicit,
        )
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-051") from refusal
    return Response(
        {
            **selectors.issued_run_dict(outcome, created=True),
            "unavailable": [dict(entry) for entry in RELEASE_UNAVAILABLE],
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def run_issue_progress(request: Any, run_id: str) -> Response:
    """`GET …/issue/progress?job=<id>` — the Send's *n of N*, the read the Send
    step polls (DEF-BIL-8710).

    The Check's own read (`GET …/check`) has handed a worker-less Check back to
    the billing worker since DEF-BIL-8511; the Send polled `GET /jobs/{id}`,
    which is the jobs kernel's and decides nothing, so a Send whose worker died
    froze for good. This read answers the same record AND, when the workers say
    nobody is on it, hands it back through `run_jobs.resume_job` — the Check's
    path, its locks and its refusal with no worker. `job` names the Send the
    screen started; without it the run's active Send is read. A job that is not
    this run's Send answers `job: null`, never another run's record.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    job = send_batches.send_job_for(run, request.query_params.get("job") or None)
    resumed = False
    if (
        job is not None
        and job["status"] == core_jobs.RUNNING
        and run_jobs.job_is_abandoned(job["id"])
    ):
        try:
            job, outcome = run_jobs.resume_job(run, job["id"])
            resumed = outcome == core_jobs.REDISPATCHED
        except BillingRuleError:
            job = core_jobs.current(job["id"])
    return Response(
        {
            "bill_run_id": str(run.pk),
            "job": (
                None
                if job is None
                else {
                    "id": job["id"],
                    "status": job["status"],
                    "progress": job.get("progress"),
                    "error": job.get("error"),
                    "resumed": resumed,
                    # DEF-BIL-8747 — a Send STOPPED by the same fault on bill
                    # after bill names its stop for the screen: its code, the
                    # catalogue key and its count. The fault's class stays in
                    # the record for support and never reaches the screen.
                    "stopped": _send_stop(job),
                }
            ),
        }
    )


def _send_stop(job: dict[str, Any]) -> dict[str, Any] | None:
    stopped = (job.get("checkpoint") or {}).get("stopped")
    if job.get("status") != core_jobs.FAILED or not isinstance(stopped, dict):
        return None
    return {
        "code": stopped.get("code"),
        "message_key": stopped.get("message_key"),
        "params": dict(stopped.get("params") or {}),
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4: Executive View on Reads & Billing runs
def billing_pending(request: Any) -> Response:
    """The Pending-billing QUEUE (11b §2.8 · US-BIL-006) — S30's chip and list.

    *"Hold ≠ forget."* This is the door back for every account a run did not
    bill: the row, its age, whether it has escalated, and WHICH DOOR it came
    through (a phase-1 hold — never calculated — or a phase-3 mark-for-later,
    which was calculated and broke at a named stage).

    `as_of` is a REQUIRED query parameter and is not defaulted to a server
    clock. Aging is measured against the TENANT's today (BR-TEN-043, gate G6),
    and a queue re-opened from another timezone must not silently age its own
    rows by a day. The refusal names the parameter rather than guessing.

    `escalation_days` is accepted for the same reason it is an argument in the
    service: the tenant setting BR-BIL-021 requires does not exist yet, so the
    story's fixture value is the DEFAULT and a caller that knows the tenant's
    number passes it. Reported in the body's `unavailable`, never implied.
    """
    require_tenant(request)
    as_of = _query_date(request, "as_of")
    escalation_days = _query_int(
        request, "escalation_days", default=pending.DEFAULT_ESCALATION_DAYS
    )
    include_resolved = str(request.query_params.get("include_resolved", "")).lower() in (
        "1",
        "true",
        "yes",
    )
    rows = pending.pending_rows(
        as_of=as_of,
        escalation_days=escalation_days,
        include_resolved=include_resolved,
    )
    return Response(
        {
            "items": [selectors.pending_row_dict(row) for row in rows],
            "counts": pending.pending_count(as_of=as_of, escalation_days=escalation_days),
            "as_of": as_of.isoformat(),
            "escalation_days": escalation_days,
            "unavailable": [dict(entry) for entry in pending.PENDING_UNAVAILABLE],
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_discard(request: Any, run_id: str) -> Response:
    """`POST /billing/runs/{id}/discard` — throw a DRAFT run away (`DEF-BIL-9255`).

    The run keeps its row as `abandoned` (BR-BIL-1045) and its draft bills go;
    an issued, signed-off or catch-up-parent run is refused by name. The whole
    rule and its reasoning are `runs.discard_run`'s docstring. Audited
    `bill_run.discarded` (hard rule 7).
    """
    from apps.billing import runs as billing_runs

    require_tenant(request)
    run = selectors.run_or_404(run_id)
    try:
        done = billing_runs.discard_run(run, actor=getattr(request, "user", None))
    except billing_runs.DiscardRefused as refused:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-1045",
            message_key=_DISCARD_REFUSALS[refused.code]["message_key"],
            params={"run_id": str(run.pk)},
        ) from refused
    return Response(done)


#: One catalogue sentence per refusal, written as literals so `G32` reads them.
_DISCARD_REFUSALS: dict[str, dict[str, str]] = {
    "not_draft": {"message_key": "billing.runDiscard.refused.notDraft"},
    "has_issued_bills": {"message_key": "billing.runDiscard.refused.hasIssued"},
    "released": {"message_key": "billing.runDiscard.refused.released"},
    "has_catch_up": {"message_key": "billing.runDiscard.refused.hasCatchUp"},
}


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def run_catch_up(request: Any, run_id: str) -> Response:
    """Start a catch-up SUB-RUN over held accounts (US-BIL-006 TC-2/5/6).

    The queue's bulk action, server-side. It writes ONE `bill_runs` row — a
    child of the run named in the path, over that run's period, scoped to a
    subset of its unresolved holds and keyed on the parent's key plus that
    scope (BR-BIL-005/015). It bills nothing: preparing, calculating and
    issuing a sub-run are the same five phases as any other run, reached
    through the same endpoints, which is US-BIL-006's own *"flowing
    drafts→issue like any run"*.

    **A duplicate is a 409 carrying who/when/link**, not a 422 — the same shape
    `POST /billing/runs` gives a repeated cycle run, because it is the same
    rule at sub-run granularity and a screen should not have to tell the two
    refusals apart.
    """
    require_tenant(request)
    parent = selectors.run_or_404(run_id)
    payload = _payload(request)
    account_ids = payload.get("account_ids")
    if not isinstance(account_ids, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.catch_up.account_ids_required",
            field_errors=[{"field": "account_ids", "code": errors.VAL_FORMAT}],
        )
    try:
        child = pending.create_catch_up_run(
            parent_run=parent,
            account_ids=[str(value) for value in account_ids],
            run_by=_actor_id(request),
            actor=getattr(request, "user", None),
        )
    except pending.DuplicateCatchUp as clash:
        existing = clash.existing
        # THE SAME CODE `POST /billing/runs` gives a repeated cycle run
        # (`BIZ_IDEMPOTENT` / BR-BIL-005) and the same three facts —
        # who ran the original, when, and the id the screen links. It is one
        # rule at two granularities, and a screen should not have to tell two
        # refusals apart to render one sentence.
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-BIL-015",
            message_key="billing.catch_up.duplicate",
            params={
                "run_id": str(existing.pk),
                "ran_by": None if existing.run_by_id is None else str(existing.run_by_id),
                "ran_at": existing.created_at.isoformat() if existing.created_at else None,
            },
        ) from clash
    except BillingRuleError as refusal:
        raise _as_catalog_refusal(refusal, "BR-BIL-015") from refusal
    return Response(
        {
            "id": str(child.pk),
            "parent_run_id": str(parent.pk),
            "status": child.status,
            "period_start": child.period_start.isoformat(),
            "period_end": child.period_end.isoformat(),
        },
        status=201,
    )


# ══════════════════════════════════════════════════════════════════════════
# S30 THE ONE-TIME BILL TAB (US-BIL-010..014) — 11b §2.8's ad-hoc rows
#
# Five complete, golden-adjacent engines shipped on 2026-08-11 and 2026-08-15
# and NOTHING in this product could reach a line of any of them: `first_bill.py`
# · `final_bill.py` · `single.py` · `backbill.py` · `penalty.py`. Hard-won law 2
# in the module that decides what a customer owes.
#
# TWO ROUTES AND NOT SIX. BR-BIL-020 makes the ad-hoc bill *"the bulk wizard in
# single-account mode"*, and its four steps are preview → exceptions → draft →
# issue. The KIND is a body field rather than a path segment for the same reason
# the engines share one pipeline: five paths would be five places for the
# account resolution, the held-period check and the scope rules to drift.
#
#     POST /billing/one-time/preview   phase 1 — writes NOTHING
#     POST /billing/one-time           phase 2 — the run row + ONE draft
#
# ISSUE IS NOT SERVED HERE AND IS NOT STUBBED. A one-time run reaches the
# existing `POST /billing/runs/{id}/issue` like any other run.
#
# ⚠ **AND IT IS NO LONGER REFUSED THERE — THIS COMMENT WAS STALE FOR TEN DAYS
# (`DEF-3153`, corrected 2026-09-02).** It read: *"is refused there today, by
# `issue.derive_due_date`, because BR-BIL-024 takes the due date from THE
# CYCLE's due-days and a one-time run has no cycle. **OQ-241** asks the PO where
# a cycle-less bill's due-days come from"*. **OQ-241 was CLOSED by the PO on
# 2026-08-23** (CR-029 D8③, verbatim: *"what due date a cycle-less one-time bill
# gets - it will be capture at the time of bulk billing - not here"*) and
# RC-W2-T4 built it: `create_one_time_run(due_days=…)` puts both the bill date
# and the due-days on the RUN, `_due_terms_for` resolves run-then-cycle, and
# `one_time_bill_cannot_be_issued_yet` was removed from `ONE_TIME_UNAVAILABLE`.
# **A cycle-less bill issues.** Proved end to end on the first bill's deposit
# line in `tests/test_cr059_cs10_collections_schedule.py` (`CR-059` CS-19).
#
# Kept and corrected rather than deleted, so a reader can find out what happened
# to the old behaviour. Mounting a second issue route would still add a second
# place for BR-BIL-005's release gate to be forgotten.
# ══════════════════════════════════════════════════════════════════════════
def _sub_periods_from(payload: dict[str, Any]) -> tuple[tuple[date, date], ...]:
    """US-BIL-013's list of recovered periods, parsed strictly or refused.

    NOT defaulted to the whole window, ever. `backbill.py` refuses to invent a
    cadence and the reason is money: 18 kgal of water priced as ONE period puts
    13 kgal in the top tier (104.50) where six monthly groups put 6 (79.50) —
    **$25.00** on one service on one bill, with the bill footing either way.
    """
    raw = payload.get("sub_periods")
    if not isinstance(raw, list):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.oneTime.subPeriodsRequired",
            field_errors=[{"field": "sub_periods", "code": errors.VAL_REQUIRED}],
        )
    windows: list[tuple[date, date]] = []
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="billing.oneTime.subPeriodInvalid",
                field_errors=[{"field": f"sub_periods[{index}]", "code": errors.VAL_FORMAT}],
            )
        windows.append((_date_field(row, "period_start"), _date_field(row, "period_end")))
    return tuple(windows)


def _one_time_request(payload: dict[str, Any]) -> one_time.OneTimeRequest:
    """Step 1's answers, and NOTHING that could carry an amount.

    ⚠ **BR-BIL-020 IS ENFORCED BY WHAT THIS FUNCTION DOES NOT READ.** The
    prototype's step 2 renders every line as an editable description and an
    editable amount with a *+ Add line* button beneath it, and that is
    superseded IN WRITING: *"lines come ONLY from rules and charge codes — free
    typed amounts never exist on any bill"*. So nothing here reads `amount`,
    `description` or `lines` from the body. A posted `amount` is not rejected
    with a message that a later refactor could delete — it is not looked at, and
    `OneTimeRequest` has no member to put it in.
    """
    kind = one_time.checked_kind(payload.get("kind"))
    sub_periods: tuple[tuple[date, date], ...] = ()
    period_start: date | None = None
    period_end: date | None = None
    if kind in one_time.SUB_PERIOD_KINDS:
        sub_periods = _sub_periods_from(payload)
    elif kind in one_time.CHARGE_CODE_KINDS:
        # A fee is charged ON a day and both ends of its window are that day, so
        # no period is read at all: `one_time.checked_window` derives the window
        # from the bill date the clerk typed and refuses by name when there is
        # none. Reading a period here as well would be the second source for one
        # window that `OneTimeRequest` exists to avoid.
        pass
    else:
        period_start = _date_field(payload, "period_start")
        period_end = _date_field(payload, "period_end")
    scope = payload.get("scope_services")
    return one_time.OneTimeRequest(
        account_id=str(payload.get("account_id") or ""),
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        # BR-BIL-070 — what the clerk typed. On a one-time run it is the ONLY
        # source of a bill date; absent stays absent (no clock, BR-TEN-043).
        bill_date=_optional_date_field(payload, "bill_date"),
        # ⚠ **THIS LINE IS `DEF-BIL-5311`, AND IT WAS MISSING RATHER THAN
        # WRONG.** ⚠ **TWO LANES FOUND IT INDEPENDENTLY ON THE SAME DAY** —
        # screen 21's lane filed it as `DEF-BIL-5311` and this one as
        # `DEF-BIL-5317`, minutes apart and neither able to see the other's
        # row, which is law 11's id collision one level up: the DEFECT was
        # duplicated, not just the number. The duplicate row was withdrawn on
        # re-derivation at push time and this cites theirs. CR-029 D8③ closed OQ-241 on 2026-08-23 — PO verbatim, *"what
        # due date a cycle-less one-time bill gets - it will be capture at the
        # time of bulk billing - not here"* — and `create_one_time_run(due_days=
        # …)`, `issue._due_terms_for`'s run-then-cycle precedence and the
        # deletion of the *cannot be issued* notice were all built for it. The
        # one thing nobody added was the line that carries the clerk's answer
        # from the request body into the dataclass, so the value resolved was
        # `None` on every one-time bill this route made and `derive_due_date`
        # refused by name at issue. This is `_optional_due_days`, the SAME
        # parser the run route uses: `0` is a lawful arrangement (due ON the
        # bill date, BR-MET-009's `due_days ≥ 0`) and is kept apart from
        # *nobody typed one* by `is None`, never by truthiness.
        due_days=_optional_due_days(payload),
        sub_periods=sub_periods,
        reason_code=str(payload.get("reason_code") or ""),
        # BR-BIL-007 — WHICH of the tenant's own charge codes a fee raises. A
        # CODE and never an amount: the figure lives on the tenant's row, so
        # this adds a choice and adds nowhere to put money.
        charge_code=str(payload.get("charge_code") or ""),
        # DEF-RAT-8753 — the amount entered for a code priced *entered when
        # used* (`per_case`, CR-010 A2). `fee_bill.charge_code_line` refuses it
        # beside any code that states its own price (BR-BIL-020).
        entered_amount=_decimal_field(payload, "entered_amount"),
        scope_services=None if scope is None else tuple(str(code) for code in scope),
        # 🔒 DEF-BIL-9076 — the services whose in-period rollover the clerk
        # ACCEPTED; any other service whose meter rolled over is held by name.
        accepted_rollovers=tuple(
            str(code) for code in (payload.get("accepted_rollovers") or ()) if code
        ),
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4 reads_billing_runs: Executive is VIEW
def one_time_preview(request: Any) -> Response:
    """S30 One-time tab step 2 (US-BIL-010..014) — *"See what they'd owe"*.

    A POST that writes nothing, and the verb is the honest one: the body carries
    a period, a kind and (for a catch-up) a list of sub-periods, which is more
    than a query string should hold, and re-previewing must not be cached by an
    intermediary — a clerk who fixes a plan and previews again must see the fix.

    Every refusal a preview can produce is a REFUSAL rather than an empty
    result. Single-account mode has one account and one waiting clerk, so
    `prepare_run`'s both-halves shape (which exists to stop one bad account
    hiding 493 others) has nothing to protect here.
    """
    require_tenant(request)
    payload = _payload(request)
    # ── 2026-09-30 · THE REDRAWN PAGE'S CONTRACT (`13-one-time-bill-api-
    # contract.md` §2, build plan A2–A4). EVERY step-1 problem is found in ONE
    # pass and refused together, each on its own field with its own key — the
    # clerk fixes the form once, not once per click (A3). The one tolerated
    # problem is an empty Days to pay: the answer carries the cycle's default
    # for the screen to prefill, so refusing for that field would hide the very
    # number that fills it.
    # `DEF-BIL-8330` — a fact about the ACCOUNT (a first bill on no cycle) is
    # a step-1 problem too, first in the screen's order, on the account field.
    problems = one_time_answer.account_problems(payload) + one_time_answer.problems_in(payload)
    if problems and not one_time_answer.only_days_to_pay_missing(problems):
        raise one_time_answer.refuse(problems)
    request_obj = one_time_answer.request_from(payload)
    captured: dict[str, Any] = {}
    try:
        internal = one_time.preview(request_obj, capture=captured)
    except GatherProblem as problem:
        raise one_time_answer.pricing_refusal(
            {
                "reason": problem.reason,
                "service_code": problem.service_code,
                "message_key": problem.message_key,
                "message_params": problem.message_params,
                "detail": str(problem),
            }
        ) from problem
    except BillingRuleError as refusal:
        raise _one_time_refusal(refusal) from refusal
    # A real setup error the engine refused on (two base codes, an unpriced
    # size, no rate version) is still a refusal — named, and naming the service
    # — never a 200 whose bill is empty (a zero on a bill preview is a money
    # claim that the customer owes nothing).
    blocked = internal.get("blocked") or []
    if internal.get("ready") == 0 and blocked:
        raise one_time_answer.pricing_refusal(blocked[0])
    if internal.get("priced") is False and (
        (internal.get("priced_unavailable") or {}).get("reason")
        not in one_time_answer.PREVIEW_WAITS_FOR_A_READING
    ):
        raise one_time_answer.pricing_refusal(internal.get("priced_unavailable") or {})
    # `DEF-BIL-8300` — a meter WAITING for its reading is not refused here: the
    # answer carries the reading rows to type it into and a bill with no total.
    # The DRAFT still refuses it (`one_time_create` below), so nothing can be
    # billed on a reading that is not saved.
    answer = one_time_answer.preview_answer(request_obj, internal=internal, captured=captured)
    if problems:
        # Only the empty Days to pay reaches here; it rides on the answer so a
        # screen that asked can still show it on its field.
        answer["field_errors"] = problems
    return Response(answer)


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def one_time_period_check(request: Any) -> Response:
    """S30 One-time bill step 1 — `DEF-BIL-10068` / `DEF-BIL-10069`.

    The same body as the preview; answers `{duplicate, closed_month}` the
    moment the period is picked, without pricing anything and without
    writing. A POST for the preview's reason: the body is a request, and a
    cached answer would hide a draft discarded a second ago. The rules and the
    PO's words are `one_time_answer.period_check`'s docstring.
    """
    require_tenant(request)
    return Response(one_time_answer.period_check(_payload(request)))


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def one_time_account(request: Any, account_id: str) -> Response:
    """S30 One-time bill step 1 — the account card, from the ACCOUNT (`DEF-BIL-8281`).

    Read the moment an account is chosen, independent of the preview: the
    preview refuses while a required step-1 field is empty, and the card's
    Plan, Cycle, Last bill and the Days-to-pay default are facts about the
    account, not about a bill. Writes nothing; another tenant's id is a 404
    through customers' own tenant-scoped read (hard rule 1).
    """
    require_tenant(request)
    return Response(one_time_answer.account_facts(account_id))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def one_time_create(request: Any) -> Response:
    """S30 One-time tab step 3 — the run row and ONE draft bill (BR-BIL-020).

    201, with the draft's own figures inline. A draft is not money (BR-BIL-004),
    so this is safe to serve as a plain create; what it is NOT is an issue, and
    the response says so by carrying `unavailable` — the tab renders it, so a
    clerk learns the bill cannot be sent yet from the screen rather than from a
    later refusal they cannot explain.

    A repeat is 409 BIZ-IDEMPOTENT with who/when/link (BR-BIL-005). That matters
    more here than on a cycle run: a double-clicked *Create bill* on a move-out
    would otherwise produce TWO final bills for one tenancy, and a final bill is
    the one nobody looks at again.
    """
    require_tenant(request)
    payload = _payload(request)
    # Contract §4 — the SAME request and the SAME all-at-once refusal as the
    # preview, with no tolerance: nothing is drafted without Days to pay
    # (BR-BIL-024, a cycle-less bill has no other source for its due date).
    # `DEF-BIL-8330` — the account's own facts first (see `one_time_preview`).
    problems = one_time_answer.account_problems(payload) + one_time_answer.problems_in(payload)
    kind = str(payload.get("kind") or "")
    problems += one_time_answer.extras_problems(payload, kind=kind)
    if problems:
        raise one_time_answer.refuse(problems)
    request_obj = one_time_answer.request_from(payload)
    try:
        body = one_time.create(
            request_obj,
            run_by=_actor_id(request),
            actor=_actor_id(request),
        )
    except runs.DuplicateRun as duplicate:
        # A8 — who billed this period already, WHEN, and the bill to open: the
        # screen's *Already billed* banner links to it by `invoice_id` and
        # prints `invoice_no` (contract §4).
        params = one_time_answer.duplicate_params(duplicate.original)
        if one_time_answer.is_draft_duplicate(params):
            # `DEF-BIL-10068` (PO 2026-10-12) — a DRAFT is not *"Already
            # billed"*: it is *"Draft already exists for this period."*, which
            # the clerk can open or discard. Still a refusal (one draft per
            # account, kind and window — BR-BIL-005); only its sentence moves.
            raise errors.BizError(
                errors.BIZ_IDEMPOTENT,
                br_ref="BR-BIL-005",
                message_key="billing.oneTime.duplicateDraft",
                params=params,
            ) from duplicate
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-BIL-005",
            message_key="billing.oneTime.duplicate",
            params=params,
        ) from duplicate
    except GatherProblem as problem:
        raise one_time_answer.pricing_refusal(
            {
                "reason": problem.reason,
                "service_code": problem.service_code,
                "message_key": problem.message_key,
                "message_params": problem.message_params,
                "detail": str(problem),
            }
        ) from problem
    except BillingRuleError as refusal:
        raise _one_time_refusal(refusal) from refusal
    answer = one_time_answer.draft_answer(body, request_obj)
    # Kept beside the contract's keys so a caller of the old shape still finds
    # them: the kind, the draft's status, and a final bill's settlement.
    answer.update(
        {
            "kind": body.get("kind"),
            "status": body.get("status"),
            "bill_type": body.get("bill_type"),
            "unavailable": body.get("unavailable") or [],
        }
    )
    if "settlement" in body:
        answer["settlement_detail"] = body["settlement"]
    return Response(answer, status=201)


def _one_time_refusal(refusal: BillingRuleError) -> errors.BizError:
    """A rule refusal on the three one-time routes — its OWN key where it has one.

    Contract §2: *"The generic `billing.run.refused` is never used on this
    route."* `_as_catalog_refusal` falls back to exactly that key, so these
    routes fall back to the one-time bill's own sentence instead. The key sits
    in the keyword position on purpose (G32/G33 read it there — see
    `_as_catalog_refusal`'s own warning).
    """
    named_key = getattr(refusal, "message_key", None)
    named_params = getattr(refusal, "params", None) or {}
    br_ref = getattr(refusal, "br_ref", None) or "BR-BIL-020"
    if named_key is not None:
        return errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=br_ref,
            message_key=named_key,
            params={**named_params, "detail": str(refusal)},
        )
    # `DEF-BIL-8288` — this fell back to `billing.oneTime.refused` (*"This
    # one-time bill can't be created as asked …"*) and the engine's reason sat
    # in `params.detail`, which is never rendered. The engine's own sentence,
    # cleaned of ids and rule codes, is the specific fallback now.
    return one_time_answer.engine_refusal(str(refusal), br_ref=br_ref)


def _approved_by_from(payload: dict[str, Any]) -> dict[str, Any] | None:
    """PO 2026-09-30 — the optional approver of a penalty bill: a staff user
    (`{"user_id": …}`) or a typed name (`{"name": …}`). Absent is lawful and is
    never refused; a present value that is neither is refused on its field."""
    raw = payload.get("approved_by")
    if raw is None or raw == {} or raw == "":
        return None
    if isinstance(raw, dict):
        user_id = str(raw.get("user_id") or "").strip()
        name = str(raw.get("name") or "").strip()
        if user_id:
            return {"user_id": user_id}
        if name:
            return {"name": name}
    raise errors.ValidationError(
        errors.VAL_FORMAT,
        message_key="billing.oneTime.err.approverInvalid",
        field_errors=[
            {
                "field": "approved_by",
                "code": errors.VAL_FORMAT,
                "message_key": "billing.oneTime.err.approverInvalid",
            }
        ],
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def one_time_send(request: Any, run_id: str) -> Response:
    """Contract §5 — *Send*: authorise and issue this run's ONE draft (US-BIL-033).

    🔒 HUMAN-REVIEW-PENDING — the door into financial immutability for every
    one-time bill; the money half is `one_time_send.send`, whose docstring is
    the long form. Row in 12-governance/09-human-review-ledger.md.

    Refused, before anything is read, unless all FIVE release confirmations
    arrive as literal `true` — compliance, email, text, autopay and final (PO
    ruling 2026-09-30, option B; each untaken one named on
    `confirmations.<name>`, `billing.oneTime.err.confirmRequired`); the run
    stays a draft and no number is spent. The single *"I checked the amounts"*
    tick this used to take is retired. `delivery` is one of three words and
    `sent_at` is the clerk's instant with its offset (BR-TEN-043 — never a
    clock). **Idempotent:** a second call answers `200` with the SAME bill.
    A cycle run's id answers 404 here: this door is for one-time runs only, and
    a cycle run is released through S31's own gate.
    """
    require_tenant(request)
    run = selectors.run_or_404(run_id)
    if not one_time_send_module.one_time_run_or_none(run):
        raise errors.deny_as_not_found()
    payload = _payload(request)
    problems: list[dict[str, Any]] = []
    # PO ruling 2026-09-30, option B, verbatim: *"B · Show all five ticks on the
    # one-time Send card."* The FIVE a cycle release asks (BR-BIL-058), each
    # ticked by the clerk. This read ONE `acknowledged` tick and recorded it as
    # all five. Anything not literal `true` is not a confirmation, and each
    # untaken one is named on its own field.
    given = payload.get("confirmations")
    given = given if isinstance(given, dict) else {}
    for name, _column in (*release.CONFIRMATION_COLUMNS, (release.FINAL_CONFIRMATION, None)):
        if given.get(name) is not True:
            problems.append(
                {
                    "field": f"confirmations.{name}",
                    "code": errors.VAL_REQUIRED,
                    "message_key": "billing.oneTime.err.confirmRequired",
                }
            )
    delivery = str(payload.get("delivery") or "")
    if delivery not in one_time_answer.DELIVERIES:
        problems.append(
            {
                "field": "delivery",
                "code": errors.VAL_UNKNOWN_LOOKUP,
                "message_key": "billing.oneTime.err.deliveryUnknown",
            }
        )
    if problems:
        raise one_time_answer.refuse(problems)
    sent_at = _datetime_field(payload, "sent_at")
    approved_by = _approved_by_from(payload)
    try:
        template_id, template_version, pin_explicit = _template_pin_for({}, run=run)
        outcome = one_time_send_module.send(
            run,
            delivery=delivery,
            sent_at=sent_at,
            template_id=template_id,
            template_version=template_version,
            template_pin_explicit=pin_explicit,
            approved_by=approved_by,
            confirmations=_confirmations_from(payload),
            confirmed_by=_actor_id(request),
            actor=getattr(request, "user", None),
        )
    except BillingRuleError as refusal:
        raise _one_time_refusal(refusal) from refusal
    body = one_time_send_module.sent_body(outcome)
    return Response(body, status=201 if outcome.created else 200)


urlpatterns = [
    path("invoices", invoices),
    path("invoices/<str:invoice_id>", invoice_item),
    # S30's One-time bill tab (US-BIL-010..014). Mounted 2026-08-16: the five
    # engines behind these two routes had shipped complete and tested and had no
    # caller outside their own test files.
    path("billing/one-time/preview", one_time_preview),
    # DEF-BIL-10068 / 10069 — step 1's duplicate and closed-month notes.
    path("billing/one-time/period-check", one_time_period_check),
    # `DEF-BIL-8281` — step 1's account card, read from the account itself.
    path("billing/one-time/accounts/<str:account_id>", one_time_account),
    path("billing/one-time", one_time_create),
    # Contract §5 (build plan A6, 2026-09-30) — the one-time bill's Send: ONE
    # call that authorises and issues this run's single draft, idempotently.
    path("billing/one-time/<str:run_id>/send", one_time_send),
    path("billing/pending", billing_pending),
    path("billing/runs", bill_runs),
    # Screen 16 step one: what a scope covers, counted, before anything is
    # created. It is not under `runs/` because no run exists when it is asked.
    path("billing/run-scope", run_scope),
    # Screen 16's DEFAULTS group — which cases carry a standing answer, what
    # each offers, and what the tenant's own setting opens it on. Beside
    # `run-scope` and not under `runs/` for the same reason: no run exists when
    # step one asks.
    path("billing/run-case-defaults", run_case_defaults),
    # CR-051 task 1 (2026-08-30) — ONE RUN, RE-OPENABLE. It was unmounted with a
    # reason that has since expired (*"the poll exists to watch a BACKGROUND
    # batch, and there is no background batch"*), and it was never only a poll:
    # nothing in the product could re-open a finished run at all. It sits ABOVE
    # the `/findings` line and every other `runs/<id>/…` route only for
    # readability — Django matches on the full pattern, so the trailing-segment
    # routes cannot be shadowed by this one.
    path("billing/runs/<str:run_id>", run_item),
    path("billing/runs/<str:run_id>/findings", run_findings),
    # The strip, without the rows — see `run_finding_counts`. Mounted BELOW
    # the findings path so the two read as the pair they are.
    path("billing/runs/<str:run_id>/findings/counts", run_finding_counts),
    # CR-051 tasks 5/6 (2026-08-30) — BR-BIL-053's break list, from the table
    # migration 0026 gives it. This route could not exist while the breaks lived
    # only in `runs.CalculatedRun.breaks`: serving it would have meant
    # calculating inside a read. It now reads rows and writes nothing, which is
    # what makes the list survive a refresh, a logout and a shift change.
    path("billing/runs/<str:run_id>/breaks", run_breaks),
    # BR-BIL-053's two ways out (DEF-2856 / DEF-2557, 2026-08-31). Both
    # engines shipped 2026-08-11 with their tests and NO HTTP caller, so the
    # break panel drew a Retry that could not act and offered no hold at all.
    path("billing/runs/<str:run_id>/breaks/<str:account_id>/retry", run_break_retry),
    path("billing/runs/<str:run_id>/breaks/<str:account_id>/hold", run_break_hold),
    # Phase 4's panel (DEF-2853, 2026-08-31). `release.summary_for` had been
    # complete since 2026-08-11 with no route, so the wizard drew "Not worked
    # out" for the customer count, the usage and the amount over a working
    # implementation — and asked a clerk to sign a release beside them.
    path("billing/runs/<str:run_id>/summary", run_summary),
    # DEF-BIL-8809 — the panel's headline alone (the bulk run page draws only
    # it), and the Sent card's "Meter reads: Locked", off the run read.
    path("billing/runs/<str:run_id>/totals", run_totals),
    path("billing/runs/<str:run_id>/read-lock", run_read_lock),
    # Step 3 of the R1–R7 cutover (decision log 2026-08-27): the disagreements
    # between the ruled pricing chain and the live path, on the pre-commit
    # stage. Mounted 2026-08-28, the day the last of the four missing facts
    # (DEF-1813) closed and the shadow could attempt a real account.
    path("billing/runs/<str:run_id>/pricing-shadow", run_pricing_shadow),
    path("billing/runs/<str:run_id>/exceptions", run_exceptions),
    path("billing/runs/<str:run_id>/exceptions/<str:case_id>/resolve", run_exception_resolve),
    path("billing/runs/<str:run_id>/catch-up", run_catch_up),
    # DEF-BIL-9255 — throw a draft run away (`run_discard`).
    path("billing/runs/<str:run_id>/discard", run_discard),
    # Phase 2 (US-BIL-004). Mounted 2026-08-16, DEF-116 — and it is the brick
    # nobody had named: with release and issue mounted the run STILL could not
    # bill anyone, because nothing in the product ever called `calculate_run`,
    # so every run reached the gate with zero drafts and the gate correctly
    # refused to authorise nothing.
    path("billing/runs/<str:run_id>/calculate", run_calculate),
    # Phase 4 and phase 5 (US-BIL-005). Mounted 2026-08-15, DEF-116: the wizard
    # had driven to a `201 draft` run and stopped, because neither of these
    # existed and its own step-5 and step-6 panels said so by name.
    path("billing/runs/<str:run_id>/release", run_release),
    path("billing/runs/<str:run_id>/issue", run_issue),
    # DEF-BIL-8710 — the Send's progress, which hands a dead worker's Send back.
    path("billing/runs/<str:run_id>/issue/progress", run_issue_progress),
    # Bulk bill run plan A3–A6 (2026-09-30) — the redrawn Check step. Its own
    # file (`check_api.py`); this line only mounts it.
    *check_api.urlpatterns,
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-025@e4b0504 (sha1[:7] of the three sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-07-bills-list.md — US-BIL-025 + US-BIL-026 — · 04-docs/05-modules/07-billing/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.8+§2.8a, the body contract; so a later change to any of them makes this stamp findable as stale in one grep. Co-packet: US-BIL-026, same three sources)
# generated: 2026-08-11 by story-coder (W3 billing read lane — the two S30 endpoints the shipped screens had been calling against a 404)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S30's list, detail and the S21 tab already ship and already call these two paths) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_us_bil_025_026_bills_read.py✔ (RED-proved first; verbatim failures in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it, so an endpoint added without it goes red)
# exceptions: (1) `f.status=past_due` REFUSES with BIZ-COMPLETENESS/BR-TEN-043 instead of falling back — a deliberate, reported deviation from BR-SHL-011's "a list URL never errors over its params", because every silent alternative states something false about a customer's money (returning the issued rows says "these are past due"; returning none says "there are none"), and neither payments nor ledger has a table to answer "unpaid". ROUTED to the PO; the i18n key `billing.past_due_not_computable` has no frontend catalogue entry yet (07-frontend is another lane's territory) so the sentence renders as its key until that lands · (2) `past_due` is null on EVERY row — served, never derived, and never computed from a wall clock (BR-TEN-043; gate G6 bans `timezone.now()` here for the same reason) · (3) `rollup.billed_this_cycle` / `billed_currency` are null: no signed document defines "this cycle" for the S30 header, and a money KPI on a guessed definition is a money claim — REPORTED as an OQ candidate · (4) `document_url` is null because `GET /invoices/{id}/document` is not mounted, and `deliveries` is null (not []) because BR-BIL-016's queue has no table · (5) `lines[].gl_account_code` is null until `ledger_accounts` (W5) and `lines[].tariff_version_label` is null because `tariff_versions` carries no version LABEL column — neither is invented · (6) `rebill_of_invoice_id` / `corrected_by_invoice_id` are null because NO COLUMN carries either citation (EP-BIL-04, W5) — served under their contracted names rather than omitted · (7) `f.issued_from` / `f.issued_to` bound the window in UTC, not the tenant's clock (BR-TEN-020/043) — a filter only, no stored or money value derives from it; REPORTED · (8) no `/document`, `/deliveries` or `/void` route is stubbed: a route that answers 501 is a promise
# [run-API lane 2026-08-11 — US-BIL-001/002/003, the four S31 routes]
# packet: US-BIL-001@990725e (sha1[:7] of the three sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md — US-BIL-001..003 — · 04-docs/05-modules/07-billing/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.8+§2.8b, the body contract this lane WROTE; co-packets US-BIL-002/US-BIL-003, same three sources)
# generated: 2026-08-11 by story-coder (W3 billing run-API lane — the routes S31's steps 2 and 3 were rendering empty against)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S31's wizard already ships and already calls all four paths; the only frontend change this lane made is deleting FINDING_TAB_BY_REASON now that `stage` is served) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_us_bil_001_003_run_api.py 20 passed / 2 skipped✔ (RED-PROVED FIRST: 4× django.urls.exceptions.Resolver404 and 9× AttributeError naming every missing symbol — verbatim in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it)
# exceptions: (1) POST /billing/runs answers 201 WITH THE ID INLINE where 11b marks the row STALE against B12 r1's 202+job_id — that law governs ASYNC operations and this queues no work. ~~and TD-17 means there is no worker to queue to~~ **THAT CLAUSE IS CORRECTED 2026-08-31 (CR-051 task 4): there IS a worker to queue to — `apps/billing/run_jobs.py` registers three kinds on billing's own `billing` queue, drained by the `celery-billing` service. The EXCEPTION still stands and its FIRST reason is the whole of it: creating a run queues no work, so there is nothing for a 202 to point at. `job_id` stays NULL here for that reason and not for the expired one — the three verbs that DO enqueue (calculate, findings, issue) answer 202 with the poll address.** `job_id` is served NULL under its contracted name; `run_id` is deliberately NOT also served (two names for one value is DEF-014's shape) · (2) ~~`bill_date` is accepted by the create and NOT STORED~~ **CLOSED 2026-08-11 — OQ-122 ruled, option A (*"A Store what they type and use it"*).** `bill_date` now lands on `bill_runs.bill_date` (migration 0011, BR-BIL-070) and IS the run's service date; absent/null/"" records that nobody typed one and the cycle's date is used. **What is NOT yet wired and is reported rather than implied:** the DUE date still derives from the cycle, because `issue._due_terms_for` reads `cycle__bill_date` and `apps/billing/issue.py` belongs to another lane in this session · (3) the findings pass REFUSES 422/BR-BIL-024 when NEITHER the run nor the cycle carries a bill date, rather than reaching for a clock (BR-TEN-043/G6) or for the period's end · (4) the findings are NOT PAGINATED where 11b §1 says "paginated": `PreparedRun` is one in-memory pass and its lists are the KPI denominator, so a page would make `ready.length` a page size · (5) every case row serves `amount`/`currency`/`quantity`/`unit` NULL and the envelope's `totals` is `{}` — `prepare_run` computes no money at all, and a zero would be a money claim · (6) `customer_name` is NULL on every case row: customers publishes only a read taking an Account INSTANCE, which billing may not import (B1/G6). REPORTED · (7) EVERY service-layer refusal becomes ONE catalog code, 422 BIZ-COMPLETENESS, with the rule's BR-ID in `br_ref` and its own sentence in `params.detail` — choosing among nine BIZ codes per refusal would be this layer interpreting rules it does not own · (8) ~~POST /billing/runs/{id}/issue is NOT SERVED and NOT STUBBED — no template pin (BR-BIL-025 has no table, BR-BIL-026 makes issue refuse without one), no event time (G6), no authorised release. Nor is the break list (it lives only in memory), the phase-4 summary or the release record (OQ-112 CLOSED: export only, no screen), or GET /billing/runs/{id} (the poll watches a background batch that does not exist)~~ **FOUR OF THE FIVE ARE CLOSED — corrected 2026-08-31 (CR-051 task 4), because a NOT-SERVED list that names four served routes is read as a plan and rebuilt.** `POST .../issue` is MOUNTED (2026-08-15, DEF-116) and `issue.issue_run` resolves BR-BIL-025's chain per account. The BREAK LIST no longer lives only in memory: migration 0026 gives it the `bill_run_breaks` table, `runs.record_break` writes a row per account as the pass finds it, and `GET /billing/runs/{id}/breaks` reads rows and writes nothing (CR-051 tasks 5/6). `GET /billing/runs/{id}` is MOUNTED (task 1), and the background batch it was said to watch is real — three registered job kinds on billing's own `billing` queue (tasks 8/9/29). **WHAT IS STILL NOT SERVED, unchanged and for its own stated reason:** the phase-4 summary as a GET and the release record as a screen — OQ-112 is CLOSED, option B, *"B An export only"*, so mounting one would implement the option the PO declined
# [CR-029 RC-W4b lane 2026-08-23 — GET /billing/runs, SET-07D's Runs tab]
# packet: CR-029 B17 §4 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) — *"**Runs** (run history, Open in Billing →)"* — plus the stated absence CycleDetailPage.tsx names in its own trailer (*"the RUN HISTORY has no endpoint (`GET /billing/runs` does not exist; only `POST`)"*)
# generated: 2026-08-23 by the RC-W4b backend lane — ONE gap. RC-W3b left it deliberately: this file was a live sibling lane's at the time and two lanes never edit one file (hard-won law 11). That lane has finished.
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the Runs tab still renders its StatedAbsence; wiring it is the frontend lane's, and the absence copy stops being true the day that lands) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr029_rcw4b_run_history.py 20 passed✔, RED-PROVED FIRST in the working tree before a line of code — `assert 405 == 200` (the path served POST only), `AttributeError: module 'apps.billing.selectors' has no attribute 'bill_runs_list'` ×9, `KeyError: 'runs'`, `assert 403 == 200` (an Executive could not read the history) · regression: tests/test_us_bil_001_003_run_api.py + tests/test_us_bil_025_026_bills_read.py + tests/test_oq122_run_bill_date.py + tests/test_cr029_rcw2_due_from_the_run.py 63 passed 5 skipped✔ · 10-scripts/03-golden-verify.py 33 PASS 0 FAIL UNCHANGED · pytest tests/golden 23 passed 1 xfailed UNCHANGED · openapi/schema.json REGENERATED (+28 −1, the one deletion being the POST description this docstring replaced)
# exceptions: (1) ~~**`run_no` IS SERVED NULL AND NOT DERIVED.** The screenshot's Run column reads `RUN-0814` and nothing in this product can produce it: `bill_runs` has no number column and `core.numbering.SERIES_CATALOG` carries no bill-run series … ROUTED to the PO for a ruling; a test holds the null~~ **CORRECTED 2026-09-15 (`DEF-BIL-5353`) — IT WAS TRUE WHEN WRITTEN ON 2026-08-23 AND STOPPED BEING TRUE THAT SAME DAY.** OQ-342 was ruled *"A: a real series (RUN-0001, like RT-001)"*, `bill_runs.run_no` exists, `runs._allocate_run_no` fills it, and the demo tenant's runs carry `RUN-0001` and `RUN-0002`. **The claim outlived the column arriving because nothing re-checks prose** (hard-won law 1: a comment claiming a GAP is not the gap), and the blueprint's §07 names this note as one of two false halves that kept screen 27 unbuilt. `run_no` is served from the column; it is NULL only on a run created before the series existed, which the ruling says stays that way — no retro-numbering — so the drawn RUN column must tolerate an absence · (2) ~~**`status` IS THE STORED COLUMN AND NOTHING EVER ADVANCES IT.**~~ **FIXED 2026-09-15 (`BR-BIL-1045`, `DEF-BIL-5352`): it advances now** — `draft` · `issuing` · `issued` · `corrected` · `abandoned`, written by `runs.record_run_outcome` from evidence at `release.release_run` and by `runs.mark_run_corrected` from the correction workflow. The original note, kept because it is the finding rather than the fix: **`status` IS THE STORED COLUMN AND NOTHING EVER ADVANCED IT.** `runs.create_run` writes `"draft"` and no writer in this module moves it — not `issue_run`, not `release`, not `pipeline` (grepped 2026-08-23) — so a Status column rendered from this field alone would title every historical run "Draft". Served anyway, because it is the row's own column and omitting it would hide the defect; SET-07D's honest *"Issued · 5 held"* composes from `issued_at` and `held`, which have evidence behind them. REPORTED as a defect — the run-status machine is not this read's to invent · (3) ~~**NO MONEY ON ANY ROW** (BR-MET-078 as hardened by CR-029, *"Money never touches these surfaces"*): `bill_run_releases.total_amount` and `invoices.total` are each one join away and neither is served, nor a currency~~ **SUPERSEDED 2026-09-15 (`DEF-BIL-5353`) — THE RULE WAS CITED ACROSS A MODULE BOUNDARY AND ITS OWN SUBJECT IS SOMEWHERE ELSE.** `BR-MET-078`'s PO wording is *"you dont need late fees in this. so dont have anything related to money when you create route and cycles"*, and its subject is r10 SET-07.3 — **the route and cycle CREATION screens**, where a clerk is setting up a schedule and has no bills to look at. A billing run's HISTORY row is neither of those, the blueprint draws a VALUE column on it (p146), and §07 calls the screen a workspace a clerk comes to for *"what did we bill last month"*. So the citation is out of scope and the column is served: Σ of the run's LOCKED bills (`INVOICE_LOCKED_STATUSES` — what actually went out) as the stored decimal string beside its `CHAR(3)` currency, CLAUDE.md rule 2, null where a run's bills carry more than one currency because a sum across two has no name. **The rule itself is untouched and still governs the screens it was written for** — quoted here rather than paraphrased so the next reader can see for themselves whether it covers the surface it is cited on, which is the habit `DEF-BIL-5353` exists to start · (4) **`issued_at` is the EARLIEST `invoices.issued_at` on the run** — a judgment where no signed rule spoke. `bill_runs` carries no issued timestamp at all; the bills do. Earliest rather than latest because the column answers *when did this run's bills go out*, and a resumed release finishing a straggler in September did not put August's batch in a customer's hand in September. REPORTED · (5) ~~the list is NOT paginated in BR-SHL-011's `page`/`per` grammar — it takes `route_read_windows`'s bounded-history posture (`limit` clamped 1…200, default 50, envelope `{"runs": [...]}`)~~ **IT IS, SINCE 2026-09-15.** `page`/`per`/`q` and three `f.` chips, envelope `{count, next, previous, results}` + `tiles`, and the 200-row ceiling is gone (`NFR-5`: no hard caps — correct at a 3,000-connection utility, 13× short of a 40,000-account one). `selectors.bill_runs_list` keeps the bounded posture for the CYCLE detail tab, which has no pager to drive. The FILTER does follow the grammar: `f.cycle_id`, the name `GET /invoices` already uses. An unreadable `f.cycle_id` answers the EMPTY list, never the whole tenant's history · (6) the per-row counts are BATCHED — 3 queries for the page whatever its length, measured at 3 for six runs carrying 24 bills and 6 holds
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
