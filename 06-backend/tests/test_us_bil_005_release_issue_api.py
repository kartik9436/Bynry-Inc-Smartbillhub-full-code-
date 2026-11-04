# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (phase 4 — the summary, the gate and the recorded
#           authorisation; phase 5 — release: issue every remaining draft and
#           stamp `released_at`)
#           Screens: S31 step 5 · S31 step 6 · S30
# Rules:    BR-BIL-058 (the gate is FIVE separately recorded facts and release
#           is refused while any is untaken) · BR-BIL-051 (phase 5 is the
#           release; the downstream work is a batch) · BR-BIL-023 (issue covers
#           all remaining drafts or a named subset) · BR-BIL-025 / BR-BIL-026
#           (the template pin is RESOLVED at issue, never invented) ·
#           BR-BIL-035 (the balance-forward figures are STAMPED at issue, so a
#           reprint shows the arrears as they stood on the bill date) ·
#           BR-BIL-004 (an issued bill is immutable) · BR-BIL-055 (a break never
#           blocks the run) · BR-TEN-043 (event time is the CALLER's — no clock
#           in a money path) · BR-TEN-003 / HR-1 (another tenant's run reads as
#           absent) · CLAUDE.md rule 2 (money + currency) · rule 6 (idempotency)
#           · rule 7 (every money action writes audit_log)
# ───────────────────────────────────────────────────────
"""DEF-116 — the two routes the bill-run wizard drove into a 404.

**THE DEFECT, VERBATIM:** *"The bill-run wizard cannot issue: neither the
release nor the issue route exists, so a run reaches READY TO BILL 0 and stops.
… Its own screens name what is missing: step 5 says 'Rule BR-BIL-058 · table
bill_run_releases — no endpoint is contracted' and step 6 says 'Rule BR-BIL-051
· POST /billing/runs/{id}/issue'. Neither route exists in the billing API."*

The engines were built, tested and correct on 2026-08-11 — `release.
authorise_release`, `release.release_run` and `issue.issue_run` all shipped with
their own suites — and `apps/billing/release.py`'s own trailer said so in as
many words: *"NOTHING CALLS THIS. There is no endpoint and no S31 step-5 screen,
so phase 4 is built and not wired."* Hard-won law 2. This file is the wire, and
the first two cases in it are the ones that would have gone red every day the
wizard was stuck.

WHY THE MOUNTING CASES COME FIRST AND ARE ASSERTED TWICE. An `api.py` that
exports `urlpatterns` no URLconf includes is not an endpoint, and every other
test in this file passes while that is true — the S30 and S31 lanes both learned
that the same way. So the routes are resolved through the REAL root URLconf and
then called over real HTTP with no session, where **401 means the route exists
and asked for one** and 404 means it does not.

WHAT THE MONEY CASES ARE ABOUT. `tc_h` is the other half of DEF-116 — *"Total
due prints `—` because the balance-forward figure is not stamped"* — worked on
the frozen WE-1 shape: a **45.00** prior bill nobody has paid, **247.87** of
current charges, and **292.87** on the page. `tc_i` is the case that stops that
fix from becoming a worse defect: on a deployment where payments publishes
nothing the figures stamp as NULLS and the bill prints the dash it printed
before. `0.00` there would tell a customer in arrears that they are square.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import documents, issue, models, payments_seam
from apps.billing.template_models import BillTemplate, BillTemplateVersion
from core import errors

from tests.isolation_helpers import requires_postgres
from tests.test_us_bil_005_issue import (
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    electric_gl_accounts,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    staff_actor,
    tenant_ctx,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: The run is confirmed at 09:40 and the bills carry 09:41 — one minute apart on
#: purpose. If the two moments were equal, a route that stamped `released_at`
#: from `confirmed_at` (or the reverse) would pass every assertion here while
#: recording the wrong instant on an immutable row.
CONFIRMED_AT = datetime(2026, 7, 3, 9, 40, tzinfo=UTC)
ISSUED_AT = datetime(2026, 7, 3, 9, 41, tzinfo=UTC)

#: ❄️ WE-1's frozen summary box (`07-billing/03-field-map.md` §Summary box):
#: **45.00 − 0.00 + 247.87 = 292.87**. The prior bill is unpaid, so the payments
#: figure is zero BECAUSE NOTHING WAS PAID rather than because nothing was read
#: — which is exactly the difference `tc_i` exists to keep visible.
PRIOR_BILL_TOTAL = Decimal("45.00")
CURRENT_CHARGES = Decimal("247.87")
TOTAL_DUE = Decimal("292.87")

ALL_FIVE = {
    "compliance": True,
    "email_mandate": True,
    "sms_mandate": True,
    "autopay_mandate": True,
    "final": True,
}


def an_actor_user(tenant, role="billing_clerk"):
    """A FakeUser carrying a REAL `users` row id.

    `bill_run_releases.confirmed_by` is an FK into identity (B2 §2), so a
    synthetic uuid would break the reviewed cross-module FK set and the
    authorisation would record a signatory who does not exist.
    """
    actor = staff_actor(tenant, role, f"{role}@release-api.test")
    return FakeUser(user_id=actor.id)


def release_call(tenant, actor_user, run, *, confirmations=None, confirmed_at=CONFIRMED_AT):
    body = {
        "confirmations": ALL_FIVE if confirmations is None else confirmations,
        "confirmed_at": None if confirmed_at is None else confirmed_at.isoformat(),
    }
    return api_call(
        billing_api.run_release,
        "post",
        user=actor_user,
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
        data=body,
    )


def issue_call(tenant, actor_user, run, **body):
    payload = {
        "issued_at": ISSUED_AT.isoformat(),
        "template_id": str(TEMPLATE_ID),
        "template_version": TEMPLATE_VERSION,
    }
    payload.update(body)
    return api_call(
        billing_api.run_issue,
        "post",
        user=actor_user,
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
        data=payload,
    )


def a_bill_of(tenant, account, run, *, invoice_no, total, **overrides):
    """A draft (or an already-issued bill) whose LINES SUM TO ITS OWN TOTAL.

    ⚠ THE TIE-OUT IS NOT COSMETIC AND THIS HELPER EXISTS BECAUSE OF IT. The
    shared `a_priced_draft` fixture writes GT-1's two frozen lines — 684 kWh ×
    $0.12 = **82.08** usage plus **18.50** base = **100.58** — and setting a
    different `total` on top of them produces a bill whose stored total and
    stamped lines disagree. `posting_seam` REFUSES exactly that, by design
    (BR-BIL-011 *"balanced by construction"*), and the run reports it as
    `posting_handoff_does_not_balance` rather than plugging the delta. Measured
    while writing this file: *"bill BL-2607-000101 does not foot: its stored
    total is 247.870000 and its stamped lines sum to 100.580000 … a difference
    of 147.290000."* So the difference is added as a REAL base line and the bill
    foots — which is what a bill of WE-1's size actually is (a multi-service
    bill), rather than a fixture with a number written on it.
    """
    from apps.tenancy import models as tenancy_models

    bill = a_priced_draft(
        tenant,
        account,
        run,
        invoice_no=invoice_no,
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        **overrides,
    )
    remainder = total - Decimal("100.58")
    if remainder:
        models.InvoiceLine.objects.create(
            tenant=tenant,
            invoice=bill,
            account=account,
            service=tenancy_models.Service.objects.get(code="electric"),
            kind="base",
            description="Electric service availability charge",
            amount=remainder,
            taxable=True,
        )
    return bill


def an_issuable_world(tenant, actor, *, total=CURRENT_CHARGES):
    """A run with ONE draft that can actually become a bill.

    The GL map has to answer or every bill breaks on BR-BIL-010, so the seeded
    chart is asserted rather than assumed — `electric_gl_accounts` fails loudly
    if the tenant was provisioned without Electric's 4100/4105 split, which is a
    fixture problem that would otherwise look like an issue defect.
    """
    electric_gl_accounts()
    run = a_run(tenant, key="2026-06|release-api")
    account = an_account(actor, tenant, account_no="ACC-1042")
    draft = a_bill_of(tenant, account, run, invoice_no="BL-2607-000101", total=total)
    return run, account, draft


# ══════════════════════════════════════════════════════════════════════════
# DEF-116 — the routes exist. Hard-won law 2, at the routing layer.
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc40__the_release_and_issue_routes_are_mounted(brazos):
    """The two paths S31's steps 5 and 6 named in their own gap panels.

    Resolved through the REAL root URLconf: `apps/billing/api.py` exporting
    `urlpatterns` is not an endpoint until `config/urls.py` includes it, and
    both of these were absent from `urlpatterns` entirely until 2026-08-15.
    """
    from django.urls import resolve

    run_id = uuid.uuid4()
    assert resolve(f"/api/brazosbend/billing/runs/{run_id}/release").func is billing_api.run_release
    assert resolve(f"/api/brazosbend/billing/runs/{run_id}/issue").func is billing_api.run_issue


def test_us_bil_005_tc40__the_release_and_issue_routes_are_reachable(brazos):
    """The other half of "mounted": a real request through the real middleware,
    authentication and permission class ARRIVES at the view.

    **401 AUTH-001 means the route exists and asked for a session. 404 is what
    both answered before this lane**, and 404 is what `runRouteAbsent` in the
    wizard was reading when it rendered "no endpoint is contracted".
    """
    from django.test import Client

    run_id = uuid.uuid4()
    for path in (
        f"/api/{brazos.subdomain}/billing/runs/{run_id}/release",
        f"/api/{brazos.subdomain}/billing/runs/{run_id}/issue",
    ):
        response = Client().post(path)
        assert response.status_code == 401, (
            f"{path} answered {response.status_code}: a 404 here means the route is still "
            "not reachable, whatever the URLconf says — which is DEF-116 exactly"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# Phase 4 — the gate (BR-BIL-058)
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc41__the_gate_records_five_facts_and_stamps_no_release(brazos, dana):
    """BR-BIL-058: five separately recorded facts, and NOTHING is billed yet.

    `released_at` is NULL on the row this route writes, which is not an omission
    — it is TC-13's resumable position. The gate is the last moment at which
    nothing has been billed, and separating it from the act is what makes a
    crash between them recoverable rather than a second signature.
    """
    with tenant_ctx(brazos):
        run, _account, draft = an_issuable_world(brazos, dana)
        actor = an_actor_user(brazos)
        response = release_call(brazos, actor, run)

    assert response.status_code == 201
    assert response.data["created"] is True
    assert response.data["confirmations"] == ALL_FIVE
    assert response.data["confirmed_at"] == CONFIRMED_AT.isoformat()
    assert response.data["confirmed_by"] == str(actor.id)
    assert response.data["released_at"] is None
    # CLAUDE.md rule 2 / DEF-099 — money never travels without its currency.
    assert response.data["currency"] == "USD"
    assert Decimal(response.data["total_amount"]) == CURRENT_CHARGES
    with tenant_ctx(brazos):
        assert models.BillRunRelease.objects.filter(bill_run=run).count() == 1
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


def test_us_bil_005_tc42__an_untaken_confirmation_refuses_and_is_named(brazos, dana):
    """US-BIL-005 TC-10 — Priya ticks four of the five and presses release.

    Refused, and the refusal NAMES the one she did not take. A gate that said
    only "incomplete" would make a clerk find it by elimination, and a gate that
    named the first missing fact one refusal at a time would make them walk the
    five toggles five times.
    """
    with tenant_ctx(brazos):
        run, _account, _draft = an_issuable_world(brazos, dana)
        response = release_call(
            brazos,
            an_actor_user(brazos),
            run,
            confirmations={**ALL_FIVE, "sms_mandate": False},
        )
        rows = models.BillRunRelease.objects.filter(bill_run=run).count()

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-BIL-058"
    assert "sms_mandate" in response.data["params"]["detail"]
    assert rows == 0, "a refused gate must not leave an authorisation row"


def test_us_bil_005_tc43__a_double_clicked_confirm_writes_one_row(brazos, dana):
    """CLAUDE.md rule 6, and US-BIL-005 TC-13's *"does NOT ask for authorisation
    a second time"* at one second's distance rather than one crash's.

    The second call answers **200 `created: false`** with the row that already
    exists — the shape `POST /accounts/{id}/payments` gives a replayed payment
    (11b §2.9b) — because a second row would be a second authorisation for one
    signature, and `bill_run_releases` is append-only (hard rule 4): there would
    be no way to take it back.
    """
    with tenant_ctx(brazos):
        run, _account, _draft = an_issuable_world(brazos, dana)
        actor = an_actor_user(brazos)
        first = release_call(brazos, actor, run)
        second = release_call(brazos, actor, run)
        rows = models.BillRunRelease.objects.filter(bill_run=run).count()

    assert first.status_code == 201 and first.data["created"] is True
    assert second.status_code == 200 and second.data["created"] is False
    assert second.data["id"] == first.data["id"]
    assert rows == 1


# ══════════════════════════════════════════════════════════════════════════
# Phase 5 — the release (BR-BIL-051)
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc44__issue_without_a_recorded_release_is_refused(brazos, dana):
    """US-BIL-005 TC-14 — *"Forged POST straight to issue with no release
    record"*.

    Refused at the door, because after the door there is no un-issuing. The
    check is here AND inside `issue_run` on purpose: a forged call straight to
    the service and a half-filled authorisation row are different bugs.
    """
    with tenant_ctx(brazos):
        run, _account, draft = an_issuable_world(brazos, dana)
        response = issue_call(brazos, an_actor_user(brazos), run)
        after = models.Invoice.objects.get(pk=draft.pk)

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-BIL-058"
    assert after.status == models.INVOICE_DRAFT and after.issued_at is None


def test_us_bil_005_tc45__release_then_issue_turns_the_draft_into_a_bill(brazos, dana):
    """The whole of DEF-116, end to end: a run that could only reach a draft now
    reaches an issued, immutable bill.

    Four facts, and each was unreachable over HTTP before this lane: the bill's
    status moves, it carries the CALLER's `issued_at` (never a clock), the
    authorisation row gains its `released_at`, and the response says what did
    and did not happen downstream — `handoffs` carries the render and the queue
    write as `ran: true` and the background batch as `ran: false`, so nobody
    reads "released" as "the customer has it".
    """
    with tenant_ctx(brazos):
        run, _account, draft = an_issuable_world(brazos, dana)
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        response = issue_call(brazos, actor, run)
        bill = models.Invoice.objects.get(pk=draft.pk)
        row = models.BillRunRelease.objects.get(bill_run=run)

    assert response.status_code == 201
    assert response.data["issued"]["issued_count"] == 1
    assert response.data["issued"]["broken"] == []
    assert bill.status == models.INVOICE_ISSUED
    assert bill.issued_at == ISSUED_AT
    assert bill.template_version == TEMPLATE_VERSION
    assert row.released_at == ISSUED_AT
    # BR-BIL-051 — "released" is not "sent", and the response says so rather
    # than leaving a caller to infer it.
    handoffs = {entry["code"]: entry["ran"] for entry in response.data["handoffs"]}
    # AMENDED 2026-08-31 (CR-051 task 4). This asserted
    # `handoffs["not_run_in_background"] is False` — the SERVED sentence that
    # told every caller there was no worker on this deployment, twelve days
    # after one landed. The claim is retracted at source; asserting its ABSENCE
    # as well as the replacement is what stops a revert passing.
    assert "not_run_in_background" not in handoffs
    assert handoffs["issue_runs_in_a_worker_when_the_caller_asks"] is True
    assert handoffs["delivery_queued_but_not_dispatched"] is True


def test_us_bil_005_tc46__a_second_issue_is_a_replay_and_never_a_second_bill(brazos, dana):
    """CLAUDE.md rule 6 — two identical issue calls must not double-issue.

    The inner guarantee is structural (`issue_run` selects the run's REMAINING
    drafts, so the second pass has nothing to find); the outer one is the route,
    which answers **200 `created: false`** with the release that is already
    stamped rather than a refusal. A double-clicked Send is a replay, not an
    error — and the bill's `issued_at` must not move, because it is the moment
    a customer was billed and the row is immutable.
    """
    with tenant_ctx(brazos):
        run, _account, draft = an_issuable_world(brazos, dana)
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        first = issue_call(brazos, actor, run)
        second = issue_call(
            brazos, actor, run, issued_at=datetime(2026, 8, 1, tzinfo=UTC).isoformat()
        )
        bill = models.Invoice.objects.get(pk=draft.pk)
        bills = models.Invoice.objects.filter(bill_run=run).count()
        releases = models.BillRunRelease.objects.filter(bill_run=run).count()

    assert first.status_code == 201
    assert second.status_code == 200 and second.data["created"] is False
    assert bills == 1 and releases == 1
    assert bill.issued_at == ISSUED_AT, "the replay must not move an immutable bill's stamp"


def test_us_bil_005_tc47__a_naive_event_time_is_refused(brazos, dana):
    """BR-TEN-043 / gate G6 — the caller names the moment, and it must be an
    INSTANT.

    `2026-07-03T09:41` is a different instant in Houston than in Chennai, so a
    bill run whose stamped moment depended on where the browser was is exactly
    BR-TEN-020's warning. Refused rather than assumed UTC: the value lands on an
    immutable row and there is no later.
    """
    with tenant_ctx(brazos):
        run, _account, _draft = an_issuable_world(brazos, dana)
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        response = issue_call(brazos, actor, run, issued_at="2026-07-03T09:41")

    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_FORMAT
    assert response.data["field_errors"][0]["field"] == "issued_at"


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-035 — the balance-forward stamp (the other half of DEF-116)
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_005_tc48__total_due_is_stamped_and_prints(brazos, dana):
    """❄️ WE-1, on the page: **45.00 − 0.00 + 247.87 = 292.87**.

    DEF-116: *"Total due prints `—` because the balance-forward figure is not
    stamped."* It is stamped now, at issue, into the locked instance — which is
    where BR-BIL-035 puts it (*"so a reprint shows the arrears as they stood on
    the bill date, never as they stand today"*) and is why this is asserted on
    the RENDERED DOCUMENT and not only in the payload: the payload key exists
    to be printed, and a stamp the renderer could not read would pass a payload
    assertion and still leave the customer holding a dash.

    The prior bill is ISSUED AND UNPAID, so `payments_credits` is `0.00`
    because nothing was paid — `tc_49` is the case where it is absent because
    nothing was read, and the two must never render the same.
    """
    with tenant_ctx(brazos):
        run, account, draft = an_issuable_world(brazos, dana)
        prior = a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000099",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        issue_call(brazos, actor, run, invoice_ids=[str(draft.pk)])
        bill = models.Invoice.objects.get(pk=draft.pk)
        page = documents.render_invoice(bill)

    assert prior.status == models.INVOICE_ISSUED
    block = bill.bill_payload["balance_forward"]
    assert Decimal(block["previous_balance"]) == PRIOR_BILL_TOTAL
    assert Decimal(block["payments_credits"]) == Decimal("0")
    assert Decimal(block["current_charges"]) == CURRENT_CHARGES
    assert Decimal(block["total_due"]) == TOTAL_DUE
    assert block["currency"] == "USD"
    # The renderer reads the three A19 §1.3 names off the payload's top level.
    printed = {field.label: field.value for field in page.summary}
    assert printed["Previous balance"] == "45.00 USD"
    assert printed["Payments & credits"] == "0.00 USD"
    assert printed["Current charges"] == "247.87 USD"
    assert printed["Total due"] == "292.87 USD"
    # OQ-117's run problem is what the PO ruled ("issue and report it"). With
    # the figure printable there is nothing left to report about it.
    assert [p.code for p in page.problems if p.code == "total_due_not_printable"] == []


def test_us_bil_005_tc49__an_unreachable_payments_seam_stamps_nulls_not_zeros(
    brazos, dana, monkeypatch
):
    """*Nobody could ask* and *this customer owes nothing* are different facts,
    and only one of them is a claim about a customer's money.

    On a deployment whose payments module publishes nothing, the arrears cannot
    be read at all. The stamp writes NULLS, the page prints the dash it printed
    before this lane, and OQ-117's run problem names the bill exactly as the PO
    ruled. `0.00` here would tell a customer in arrears that they are square, on
    a page that is immutable the moment it is written.
    """
    monkeypatch.setattr(payments_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        run, account, draft = an_issuable_world(brazos, dana)
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000098",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        issue_call(brazos, actor, run, invoice_ids=[str(draft.pk)])
        bill = models.Invoice.objects.get(pk=draft.pk)
        page = documents.render_invoice(bill)

    block = bill.bill_payload["balance_forward"]
    assert block["previous_balance"] is None
    assert block["payments_credits"] is None
    assert block["total_due"] is None
    assert block["current_charges"] == "247.870000", "the bill's own figure is never in doubt"
    assert [entry["code"] for entry in block["problems"]] == [
        "payments_open_invoices_for_account_not_published"
    ]
    printed = {field.label: field.value for field in page.summary}
    assert printed["Total due"] == documents.ABSENT_MARK
    assert "total_due_not_printable" in {problem.code for problem in page.problems}


def test_us_bil_005_tc50__the_stamp_is_recorded_in_the_audit_trail(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — issue is a money action and the ARREARS are money.

    A trail row carrying only the current charges could not answer *"what did
    this bill say they owed?"* after a dispute, which is the one question the
    trail exists for on a document nobody can change afterwards.

    ⚠ **`audit_log.entity_id` IS A UUIDField AND THE ROW IS READ THROUGH THE
    BE-03 SINK, NOT THE ORM.** `audit_log` is partitioned and its primary key is
    composite, so a naive `.filter(...).first()` answered None here while the
    row existed — measured, and the reason this case reads the sink every other
    audit assertion in this repo reads. It is the same field DEF-117 was about
    from the other side: a non-UUID handed to it raises `ValueError: badly
    formed hexadecimal UUID string` AFTER the money has moved.
    """
    with tenant_ctx(brazos):
        run, account, draft = an_issuable_world(brazos, dana)
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000097",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        issue_call(brazos, actor, run, invoice_ids=[str(draft.pk)])
        rows = [
            row
            for row in audit_rows
            if row["action"] == "invoice.issued" and row["entity_id"] == str(draft.pk)
        ]

    assert len(rows) == 1, "one issued bill, one money-action trail row (hard rule 7)"
    stamped = rows[0]["after"]["balance_forward"]
    assert Decimal(stamped["total_due"]) == TOTAL_DUE
    assert stamped["currency"] == "USD"
    assert stamped["basis"] == issue.BALANCE_FORWARD_BASIS


# ══════════════════════════════════════════════════════════════════════════
# Isolation — HR-1
# ══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_us_bil_005_tc51__another_tenants_run_cannot_be_released_or_issued(brazos, lonestar, dana):
    """HR-1 / BR-TEN-003 — a run id from another utility reads as ABSENT.

    Not "forbidden", which would confirm the run exists. Both routes take the
    run through the same `run_or_404` every other run route uses, so a
    cross-tenant id, an unknown id and a malformed id are one answer.
    """
    with tenant_ctx(brazos):
        run, _account, _draft = an_issuable_world(brazos, dana)
    with tenant_ctx(lonestar):
        actor = an_actor_user(lonestar)
        released = release_call(lonestar, actor, run)
        issued = issue_call(lonestar, actor, run)
        rows = models.BillRunRelease.objects.filter(bill_run_id=run.pk).count()

    assert released.status_code == 404 and issued.status_code == 404
    assert rows == 0


def test_us_bil_005_tc52__a_partial_template_pin_is_refused(brazos, dana):
    """BR-BIL-026 — half a pin is not a pin.

    An id with no version would otherwise get the RESOLVED version silently
    attached to it, and the bill would record a pair nobody chose. The columns
    freeze with the money (billing 0002), so there is no later correction.
    """
    with tenant_ctx(brazos):
        run, _account, _draft = an_issuable_world(brazos, dana)
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        response = api_call(
            billing_api.run_issue,
            "post",
            user=actor,
            role="billing_clerk",
            tenant=brazos,
            run_id=str(run.pk),
            data={"issued_at": ISSUED_AT.isoformat(), "template_id": str(TEMPLATE_ID)},
        )

    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_FORMAT


def test_us_bil_005_tc53__no_template_and_no_pin_refuses_by_the_rule(brazos, dana):
    """BR-BIL-025 — a tenant with no bill template cannot issue, and is told why.

    This is the refusal that replaced *"a route that issued bills on an invented
    template pin is worse than either"*. Nothing is invented: the resolution
    order is asked for, it finds nothing, and the sentence names the rule and
    the reason a pin is not optional (a reprint renders from it forever).

    ⚠ **CORRECTED 2026-08-16 (DEF-123 CLOSED).** This docstring read *"NO TENANT
    IN THIS PRODUCT HAS A BILL TEMPLATE TODAY — nothing creates one, the S8
    Templates tab has no endpoint, and provisioning has no billing seeder. So
    this refusal is not an edge case, it is every tenant"*, and that was exactly
    true for one day: every bill run on every deployment refused here.
    Provisioning now seeds the fallback template through
    `apps.tenancy.seams.seed_bill_templates`, and the `brazos` fixture is a
    REALLY provisioned tenant, so it now has a pin and this route answers 201.

    The case is kept, and the tenant's templates are removed inside it, because
    the refusal is still the right answer and must stay proved: a deployment
    that loses the seam has to REFUSE rather than issue on an invented pin — a
    bill in the world that cannot say what rendered it is worse than a bill that
    did not issue (BR-BIL-026/033). Deleting the rows is the only way to reach
    that state now, and reaching it deliberately is the point.
    """
    with tenant_ctx(brazos):
        run, _account, _draft = an_issuable_world(brazos, dana)
        # The state DEF-123 put every tenant in, reached on purpose.
        BillTemplateVersion.objects.all().delete()
        BillTemplate.objects.all().delete()
        actor = an_actor_user(brazos)
        release_call(brazos, actor, run)
        response = api_call(
            billing_api.run_issue,
            "post",
            user=actor,
            role="billing_clerk",
            tenant=brazos,
            run_id=str(run.pk),
            data={"issued_at": ISSUED_AT.isoformat()},
        )

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-BIL-025"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005 (04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md
#         US-BIL-005 §1/§3 · 07-billing/02-business-rules.md BR-BIL-035/051/058 ·
#         04-docs/01-spec/11b-api-audit.md §2.8 + §2.8b · 12-governance/
#         10-defect-log.csv DEF-116)
# generated: 2026-08-15 by story-coder (DEF-116 lane — the phase-4 gate route,
#         the phase-5 release route, and BR-BIL-035's balance-forward stamp)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
