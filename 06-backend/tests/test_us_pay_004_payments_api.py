# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (POST /accounts/{id}/payments — the S22/S35 Record
#           modal's exit: both BR-PAY-021 dates, the allocation choice, the
#           idempotent submit) · US-PAY-004 (GET /payments — the S33
#           Record-payments ledger, its capability row and its "Applied to"
#           column)
#           Screens: S22 · S33 · S35
# Rules:    BR-PAY-001 (the staff allocation choice) · BR-PAY-002 (the ledger
#           mutates nothing — no PUT/PATCH/DELETE exists) · BR-PAY-010
#           (allocation order) · BR-PAY-012 (purpose) · BR-PAY-021 (posting
#           date ≠ clearing date — both are first-class columns AND filters) ·
#           BR-PAY-022 (the single-entry field set) · BR-PAY-026 (method is a
#           tenant LOOKUP, six seeds, nothing hardcoded) · BR-PAY-027 (S33 =
#           the full IS-5 capability row) · BR-PAY-028 (idempotent submit) ·
#           BR-PAY-033 (the posting date is USER-ENTERED — the server stamps no
#           clock) · BR-PAY-036 (a payment is always accepted) · BR-SHL-011
#           (list grammar q/sort/dir/page/per/f.<name>) · BR-SHL-025 /
#           BR-IDN-009 (server-enforced RBAC — A4 `payments_record`:
#           System Admin Full · Billing Clerk Full · Executive View) ·
#           BR-TEN-003 / HR-1 (cross-tenant reads as absent) · BR-TEN-043
#           (event time is an input) · CLAUDE.md rule 1 · rule 2 · rule 4 ·
#           rule 6 · rule 7
# ───────────────────────────────────────────────────────
"""The two payments endpoints — and the proof that they are actually REACHABLE.

WHY THIS FILE EXISTS. On 2026-08-11 the payments WRITE PATH landed complete:
`apps/payments/models.py` has the two tables under RLS, `services.record_payment`
records a payment, allocates it and posts it to the books, and nineteen tests
hold it. `apps/payments/api.py` was ONE LINE — a docstring, no `urlpatterns` —
so no human being could record a payment. Hard-won law 2, at feature scale: the
feature exists and nobody can reach it.

THE FIRST TWO CASES ARE THE ONES THAT MATTER MOST, and they are deliberately
about plumbing rather than about money. An `api.py` that exports `urlpatterns`
is not an endpoint until `config/urls.py` includes it, and a route the URLconf
knows is not reachable until a real request survives the middleware, the
authentication and the permission class. So the routes are resolved through the
REAL root URLconf, and then called over real HTTP with no session: **401 means
the route exists and asked for a sign-in; 404 means there is no route at all**,
which is exactly what both paths answered before this lane.

EVERY NEGATIVE ASSERTION HERE IS DELIBERATE. The easy way to make an S33 row
look finished is to fill it: `receipt_no: "RCT-2608-000001"` because a receipt
"should" exist, `deposit_batch_id` because the column is there, a `days_late`
because the prototype prints one. Every one of those is a sentence about a
customer's money that no row in this database supports. So this file asserts
that they are served NULL under their contracted names, with the reason living
in the selector's docstring.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from core import errors

from apps.payments import api as payments_api
from apps.payments import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_us_pay_001_record_payment import (
    CLEARED_AT,
    NEW_BILL_TOTAL,
    OLD_BILL_TOTAL,
    PE1_CHECK,
    POSTED_AT,
    an_issued_bill,
    pe1_bills,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: The S22 form's own client token (BR-PAY-028). The API REQUIRES one, because
#: a submit that cannot dedupe is hard rule 6 with the guard removed.
TOKEN = "3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10"

#: US-PAY-001 TC-2's two-date fixture, as the SCREEN sends it — calendar dates,
#: because that is what the S22 date field collects (BR-PAY-033 pre-fills one
#: and the clerk may override it).
TC2_POSTED_DAY = "2026-08-22"
TC2_CLEARED_DAY = "2026-08-25"


# ── helpers ─────────────────────────────────────────────────────────────────
def record(tenant, actor_user, account, *, role="billing_clerk", **body):
    """POST /accounts/{id}/payments exactly as the S22 modal submits it."""
    payload = {
        "amount": str(PE1_CHECK),
        "posted_at": "2026-08-08",
        "cleared_at": "2026-08-08",
        "confirmation": "8842",
        "idempotency_key": str(uuid.uuid4()),
    }
    payload.update(body)
    return api_call(
        payments_api.account_payments,
        "post",
        user=actor_user,
        role=role,
        tenant=tenant,
        data=payload,
        account_id=str(account.pk),
    )


def listed(tenant, role="billing_clerk", **query):
    return api_call(
        payments_api.payments,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        query=query or None,
    )


def a_recorded_payment(tenant, actor, account, **overrides):
    """One CLEARED payment through the real service — the row S33 lists."""
    from apps.payments import services

    values = dict(
        account_id=account.pk,
        amount=PE1_CHECK,
        posted_at=POSTED_AT,
        cleared_at=CLEARED_AT,
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return services.record_payment(actor, **values)


def numbers_of(response):
    return [row["payment_no"] for row in response.data["results"]]


# ══════════════════════════════════════════════════════════════════════════
# The two cases this lane exists for — is the feature REACHABLE at all?
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_004_tc0__the_payment_routes_are_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer — the defect that opened this lane.

    `apps/payments/api.py` exporting `urlpatterns` is not an endpoint until
    `config/urls.py` includes it. This resolves the REAL paths through the REAL
    root URLconf, so a forgotten one-line include goes red here rather than in
    a support ticket.
    """
    from django.urls import resolve

    assert resolve("/api/brazosbend/payments").func is payments_api.payments
    assert (
        resolve(f"/api/brazosbend/accounts/{uuid.uuid4()}/payments").func
        is payments_api.account_payments
    )


def test_us_pay_004_tc0__the_routes_are_reachable_through_the_whole_stack(brazos):
    """The other half of "mounted": a real HTTP request ARRIVES at these views.

    `resolve()` proves the URLconf knows the path. It does not prove a request
    can get there — the tenant middleware, the session authentication and the
    permission class all sit in front, and any one of them answering 404 leaves
    S22 and S33 exactly as broken as they were. So an UNAUTHENTICATED call is
    made and its refusal is read: **401 AUTH-001 = the route exists and asked
    for a session; 404 = there is no route**, which is what both answered
    before this lane.
    """
    from django.test import Client

    probes = (
        ("get", f"/api/{brazos.subdomain}/payments"),
        ("post", f"/api/{brazos.subdomain}/accounts/{uuid.uuid4()}/payments"),
    )
    for method, path in probes:
        response = getattr(Client(), method)(path)
        assert response.status_code == 401, (
            f"{method.upper()} {path} answered {response.status_code}: a 404 here means the "
            "route is still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-001 — POST /accounts/{id}/payments (the S22 / S35 Record modal)
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_001_tc1__the_endpoint_records_the_pe1_check_and_says_what_it_paid(
    brazos, marcus, audit_rows
):
    """PE-1 over HTTP: check #8842, $292.87, settles $45.00 then $247.87.

    The response is what the S22 modal renders as its result — not a bare id.
    A clerk who has just taken $292.87 has to be shown WHAT IT PAID, and the
    allocator computed exactly that inside the same transaction.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        response = record(brazos, marcus.user, account)

    assert response.status_code == 201
    body = response.data
    assert body["created"] is True
    # CR-186-BRC10 (PO 2026-10-21): posted at entry, cleared at reconciliation.
    assert body["status"] == models.PAYMENT_POSTED
    assert body["payment_no"], "BR-TEN-035: the PMT- number is minted at record"
    # CLAUDE.md rule 2 — decimal STRINGS, never numbers, and the CHAR(3) rides along.
    assert body["amount"] == "292.870000"
    assert body["currency"] == "USD"
    assert body["applied"] == "292.870000"
    assert body["credit_carried"] == "0.000000"
    assert [(row["invoice_number"], row["amount"]) for row in body["allocations"]] == [
        ("BL-2607-018311", "45.000000"),
        ("BL-2608-018410", "247.870000"),
    ]
    # CLAUDE.md rule 5 — the payment REACHED THE BOOKS, and the result says so
    # as a value a caller can assert rather than a sentence it must parse.
    assert body["posted_to_ledger"] is True
    assert body["journal_entry_id"] is not None
    # hard rule 7 — both money events, written in the service's transaction.
    assert [row["action"] for row in audit_rows].count("payment.recorded") == 1
    assert [row["action"] for row in audit_rows].count("payment.allocated") == 1


def test_us_pay_001_tc2__the_endpoint_takes_BOTH_dates_and_reads_no_clock(brazos, marcus):
    """BR-PAY-021 + BR-PAY-033 + gate G6, at the boundary where a clock is easiest.

    "Check posted Aug 22 (= the due date), cleared Aug 25." The PO ruled on it
    directly on 2026-08-11: *"posting and actual dates can differ; ask actual
    date to user."* So the endpoint COLLECTS both and INVENTS neither — a
    `posted_at` defaulted to the moment the request happened to arrive would let
    network latency decide whether a customer owes a late fee.

    The absence is asserted directly as well as behaviourally: a clock added to
    this layer later would be invisible to a test that only checks the values it
    was handed.
    """
    import inspect

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        response = record(
            brazos,
            marcus.user,
            account,
            posted_at=TC2_POSTED_DAY,
            cleared_at=TC2_CLEARED_DAY,
        )

        payment = models.Payment.objects.get(pk=response.data["id"])
        assert payment.posted_at.date() == date(2026, 8, 22)
        # CR-186-BRC10: a typed clearing date is accepted and NOT stored — the
        # bank reconciliation writes it, once, with the bank's date.
        assert payment.cleared_at is None

    source = inspect.getsource(payments_api)
    assert "timezone.now()" not in source
    assert "datetime.now(" not in source
    assert "date.today(" not in source


def test_us_pay_001_tc11__a_payment_with_no_clearing_date_is_processing(brazos, marcus):
    """BR-PAY-021 — a blank clearing date is a LEGAL state, not a missing value.

    The money has not arrived, so no bill leaves arrears and nothing reaches the
    books. The result carries the reason as a CODE the screen groups on, so the
    modal can say why nothing was applied instead of showing a silent zero.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        response = record(brazos, marcus.user, account, cleared_at=None)

    assert response.status_code == 201
    # ⚠ SUPERSEDED 2026-10-21 (CR-186-BRC10): a blank clearing date no longer
    # means processing — the payment is POSTED, applied and journalled at once.
    assert response.data["status"] == models.PAYMENT_POSTED
    assert response.data["posted_to_ledger"] is True
    assert response.data["journal_entry_id"] is not None
    return
    codes = {problem["code"] for problem in response.data["problems"]}
    assert "not_cleared_so_not_allocated" in codes


def test_us_pay_001_tc5__zero_negative_and_a_missing_posting_date_are_refused(brazos, marcus):
    """US-PAY-001 TC-5 — and every refusal is a CATALOG exception (gate G9).

    `PaymentRuleError` is deliberately not a catalog exception (it is raised
    inside batches that answer no request), so THIS layer is where it becomes
    one — 422 BIZ-COMPLETENESS carrying the rule's BR-ID and its own sentence.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)

        zero = record(brazos, marcus.user, account, amount="0")
        assert zero.status_code == 422
        assert zero.data["code"] == errors.BIZ_COMPLETENESS
        assert zero.data["br_ref"] == "BR-PAY-002"
        assert "greater than zero" in zero.data["params"]["detail"]

        negative = record(brazos, marcus.user, account, amount="-10.00")
        assert negative.status_code == 422

        # A money amount that is not a number at all never reaches the service:
        # it is a VAL-002 naming the FIELD, so the modal can put it under the
        # input (US-SHL-009 renders `field_errors` there). 422 rather than 400
        # because B12 §3 maps the whole VAL class to 422 in this product.
        garbled = record(brazos, marcus.user, account, amount="two hundred")
        assert garbled.status_code == 422
        assert garbled.data["code"] == errors.VAL_FORMAT
        assert garbled.data["field_errors"][0]["field"] == "amount"

        # BR-PAY-033 — the posting date is the USER's and this layer will not
        # stamp one on their behalf.
        undated = record(brazos, marcus.user, account, posted_at=None)
        assert undated.status_code == 422
        assert undated.data["code"] == errors.VAL_REQUIRED
        assert undated.data["field_errors"][0]["field"] == "posted_at"

        assert models.Payment.objects.count() == 0, "nothing partial is written"


def test_us_pay_001_tc6__a_double_submit_through_the_endpoint_records_one_payment(
    brazos, marcus, audit_rows
):
    """US-PAY-001 TC-6 — "Double-click Record ✓ → One row only".

    The costliest bug this module could ship: the same money taken twice, the
    customer's balance wrong by the payment amount and the books out against the
    bank by the same. The client token travels as `idempotency_key`, and a
    replay answers **200 with the ORIGINAL payment and `created: false`** rather
    than 409.

    THE 409 QUESTION, ANSWERED WHERE IT IS ASKED. 11b §3 G7 lists four
    idempotent operations whose duplicate is a 409 — bill runs, read/payment
    IMPORTS, webhooks, tenant provisioning. A staff double-click is none of
    them: BR-PAY-028's own field-map row reads *"duplicate submit → single
    row"*, and G7's own list already contains the same shape (`POST /tenants`
    "repeat returns existing tenant"). A 409 toast for a button that worked is
    a wrong answer a clerk would act on.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        first = record(brazos, marcus.user, account, idempotency_key=TOKEN)
        second = record(brazos, marcus.user, account, idempotency_key=TOKEN)

    assert first.status_code == 201 and first.data["created"] is True
    assert second.status_code == 200 and second.data["created"] is False
    assert second.data["id"] == first.data["id"]
    assert second.data["amount"] == first.data["amount"], "the money is not doubled"
    assert any(p["code"] == "duplicate_submit_ignored" for p in second.data["problems"])
    assert models.Payment.objects.count() == 1
    assert [row["action"] for row in audit_rows].count("payment.recorded") == 1


def test_us_pay_001_tc6c__a_replay_never_reaches_the_write_path_at_all(brazos, marcus, monkeypatch):
    """DEF-058 — the guard that was switched off, with a test that BITES.

    `record_payment` documents two idempotency guards: a cheap pre-insert SELECT
    (what a real double-click hits) and the `uq_payments_webhook_key` index
    (what a genuine race hits). The SELECT had been replaced by
    `already = None  # RED PROOF — pre-insert lookup removed` and committed in
    that state, and **nothing went red**: the index catches the duplicate one
    layer down, so every existing case still passed. That is why this case is
    written the way it is.

    The observable difference is not the outcome — it is the PATH. Without the
    lookup a replay opens a transaction and allocates a PMT- number from the
    tenant series before the index refuses the insert and rolls it back. So the
    numbering kernel is made to explode if it is touched: with the guard in
    place a replay never reaches it, and with the guard removed this fails
    naming the exact line.

    PROVED RED by re-applying the `already = None` line: `RuntimeError: a replay
    reached numbering.next_number — the pre-insert idempotency lookup is gone
    (DEF-058)`.
    """
    from core import numbering

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        first = record(brazos, marcus.user, account, idempotency_key=TOKEN)

        def exploding_next_number(*_args, **_kwargs):
            raise RuntimeError(
                "a replay reached numbering.next_number — the pre-insert idempotency "
                "lookup is gone (DEF-058)"
            )

        monkeypatch.setattr(numbering, "next_number", exploding_next_number)
        replay = record(brazos, marcus.user, account, idempotency_key=TOKEN)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.data["created"] is False
    assert replay.data["id"] == first.data["id"]


def test_us_pay_001_tc6b__a_submit_with_no_idempotency_key_is_refused(brazos, marcus):
    """Hard rule 6, at the only layer that can enforce it for the S22 form.

    `record_payment` stores no key when the caller names none, and a double
    submit then records two payments. The service says so in its own docstring
    — *"the caller that owns a submit button must pass one, and the API layer
    will"*. This is that layer keeping the promise, and REFUSING is the only
    honest way to keep it: generating a key here would produce a different
    string on the second submit and dedupe nothing while looking as if it had.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        response = record(brazos, marcus.user, account, idempotency_key=None)

    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_REQUIRED
    assert response.data["field_errors"][0]["field"] == "idempotency_key"
    assert models.Payment.objects.count() == 0


def test_us_pay_001_tc4__the_staff_allocation_choice_reaches_the_allocator(brazos, marcus):
    """BR-PAY-001 — "default rules; specific / carry credit / split".

    The instruction is passed STRAIGHT THROUGH to `allocation.allocate_payment`;
    nothing in the API layer re-implements a line of it. Carry-credit is the
    case that proves the plumbing: the bills are untouched and the whole payment
    becomes the account credit US-PAY-007 will own.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        carried = record(brazos, marcus.user, account, apply_to="carry_credit")
        assert carried.status_code == 201
        assert carried.data["applied"] == "0.000000"
        assert carried.data["credit_carried"] == "292.870000"
        assert carried.data["allocations"] == []

    with tenant_ctx(brazos):
        specific = record(
            brazos,
            marcus.user,
            account,
            amount="45.00",
            apply_to="specific",
            targets=[{"invoice_number": "BL-2607-018311"}],
        )
        assert specific.status_code == 201
        assert [row["invoice_number"] for row in specific.data["allocations"]] == ["BL-2607-018311"]


def test_us_pay_001_tc12__an_unsupported_purpose_is_refused_by_name(brazos, marcus):
    """BR-PAY-012 — ⚠ **SUPERSEDED IN PART 2026-08-15 by US-PAY-002.**

    This case used to assert that a `deposit` purpose was REFUSED with a 422,
    because the linkage BR-PAY-012 requires did not exist. US-PAY-002 built it
    (`apps/payments/purposes.py`), so all four purposes now record and the
    refusal it asserted is gone. The test is REWRITTEN rather than deleted, for
    the reason hard-won law 1 gives: a reader comparing this file against the
    old behaviour must find out what happened to it.

    WHAT STILL HOLDS, and is what this case now asserts: a purpose whose linkage
    cannot be made is still refused BY NAME with nothing written — `plan_down`
    against an account with no live plan is the case that survives, and it is
    US-PAY-002 TC-5 verbatim (*"Rejected with a named linkage error; no orphan
    purpose links"*).

    A FIFTH purpose is still impossible: the closed set is BR-PAY-012's four.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        # The linkage that CAN still fail: a plan-down with no plan behind it.
        response = record(brazos, marcus.user, account, purpose="plan_down")

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert "no live payment plan" in response.data["params"]["detail"]
    assert models.Payment.objects.count() == 0


def test_us_pay_001_tc12b__a_deposit_purpose_now_records_and_is_not_credit(brazos, marcus):
    """US-PAY-002 TC-1 through the ENDPOINT — the other half of the supersession.

    A deposit is recorded, meets no bill and becomes no account credit; the
    response carries what is still owed on billing's side rather than implying
    the first-bill line has been satisfied.
    """
    from apps.payments import selectors

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        response = record(brazos, marcus.user, account, purpose="deposit")

    assert response.status_code == 201
    with tenant_ctx(brazos):
        assert selectors.account_credit_position(account.pk) == Decimal("0")
    codes = {problem["code"] for problem in response.data["problems"]}
    assert "first_bill_deposit_line_not_satisfied" in codes


def test_us_pay_001__an_executive_may_read_the_ledger_but_never_record(brazos, marcus):
    """A4 `payments_record`: System Admin Full · Billing Clerk Full · Executive
    View. BR-SHL-025 is SERVER-enforced — a disabled button is a courtesy."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        refused = record(brazos, marcus.user, account, role="executive")
        readable = listed(brazos, role="executive")

    assert refused.status_code == 403
    assert readable.status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# US-PAY-004 — GET /payments (the S33 Record-payments ledger)
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_004_tc1__the_ledger_serves_the_s33_row_field_for_field(brazos, marcus):
    """US-PAY-004 §5 — every name here is the one the frontend declares.

    The key set is asserted EXACTLY rather than sampled: a rename on either side
    is a broken screen, and the two halves of this contract are written down in
    two files that no compiler compares.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        a_recorded_payment(brazos, marcus, account, method_code="check")

        response = listed(brazos)

    assert response.status_code == 200
    assert set(response.data) == {
        "count",
        "next",
        "previous",
        "results",
        "totals",
        "methods",
    }
    row = response.data["results"][0]
    assert set(row) == {
        "id",
        "payment_no",
        "account_id",
        "account_no",
        "customer_name",
        "type",
        "method",
        "method_name",
        "confirmation",
        "memo",
        "amount",
        "currency",
        "status",
        "purpose",
        "posted_at",
        "cleared_at",
        "applied_to",
        "applied_total",
        "deposit_batch_id",
        "receipt_no",
    }
    assert row["type"] == models.PAYMENT_TYPE_PAYMENT
    assert row["status"] == models.PAYMENT_CLEARED
    assert row["purpose"] == models.PURPOSE_BILL
    assert row["method"] == "check"
    assert row["method_name"]
    assert row["confirmation"] == "8842"
    assert row["amount"] == "292.870000"
    assert row["currency"] == "USD"
    # BR-PAY-021: BOTH dates are first-class columns, always available.
    assert row["posted_at"] is not None
    assert row["cleared_at"] is not None
    # The prototype's "Applied to" column — the read-model over `allocations`,
    # which lists ALL of a multi-allocation row rather than the first.
    assert [entry["invoice_number"] for entry in row["applied_to"]] == [
        "BL-2607-018311",
        "BL-2608-018410",
    ]
    assert [entry["amount"] for entry in row["applied_to"]] == ["45.000000", "247.870000"]
    assert row["applied_total"] == "292.870000"


def test_us_pay_004_tc1__what_the_row_cannot_answer_is_null_under_its_own_name(brazos, marcus):
    """Serve nothing you cannot honestly compute — and never rename it away.

    Two IS-5 columns have no source in this deployment and BOTH are served null
    rather than dropped, so the screen can say WHY the cell is empty instead of
    the clerk wondering whether the data failed to load:

      · `receipt_no` — BR-PAY-024 auto-queues a receipt on every cleared
        payment (RCT- series). That queue write is US-PAY-025 / EP-PAY-07 and
        does not exist; a number here would name a receipt nobody sent.
      · `deposit_batch_id` — `deposit_batches` is EP-PAY-06's table and is not
        built. The column exists (a deferred FK, B11 F-3) and nothing writes it.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        a_recorded_payment(brazos, marcus, account)

        row = listed(brazos).data["results"][0]

    assert row["receipt_no"] is None
    assert row["deposit_batch_id"] is None


def test_us_pay_004_tc1__the_default_sort_is_posting_date_descending(brazos, marcus):
    """The capability row's own default (`posted_at desc`), and IS-2's law that
    an absent `dir` takes the SCREEN's default rather than the parser's `asc` —
    which on a growing ledger would put the oldest payment on page 1."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        older = a_recorded_payment(
            brazos,
            marcus,
            account,
            amount=Decimal("10.00"),
            posted_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        newer = a_recorded_payment(
            brazos,
            marcus,
            account,
            amount=Decimal("20.00"),
            posted_at=datetime(2026, 8, 9, 9, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 9, 9, 0, tzinfo=UTC),
        )

        default = listed(brazos)
        ascending = listed(brazos, sort="posted_at", dir="asc")

    assert numbers_of(default) == [newer.payment_no, older.payment_no]
    assert numbers_of(ascending) == [older.payment_no, newer.payment_no]


def test_us_pay_004_tc2__the_capability_rows_filters_and_search_all_work(brazos, marcus):
    """US-PAY-004 / BR-PAY-027 — the IS-5 row, verbatim: search on account #,
    customer and confirmation #; filters on type, method, status, purpose and
    BOTH date ranges (BR-PAY-021).

    The date-range pair is the one that has to be tested with dates that DIFFER:
    with posting and clearing equal, a filter reading the wrong column would
    give the right answer.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        cleared = a_recorded_payment(
            brazos,
            marcus,
            account,
            method_code="check",
            confirmation="8842",
            posted_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 25, 9, 0, tzinfo=UTC),
        )
        processing = a_recorded_payment(
            brazos,
            marcus,
            account,
            amount=Decimal("15.00"),
            method_code="ach",
            confirmation="ACH-2028091",
            posted_at=datetime(2026, 8, 23, 9, 0, tzinfo=UTC),
            cleared_at=None,
        )

        # CR-186-BRC10 — both are POSTED (neither is reconciled with the bank).
        by_status = listed(brazos, **{"f.status": models.PAYMENT_POSTED})
        by_method = listed(brazos, **{"f.method": "check"})
        by_purpose = listed(brazos, **{"f.purpose": models.PURPOSE_BILL})
        by_type = listed(brazos, **{"f.type": models.PAYMENT_TYPE_CREDIT})
        by_account = listed(brazos, **{"f.account_id": str(account.pk)})
        by_confirmation = listed(brazos, q="ACH-2028091")
        by_account_no = listed(brazos, q="A-10432")
        posted_window = listed(brazos, **{"f.posted_from": "2026-08-23"})
        cleared_window = listed(brazos, **{"f.cleared_to": "2026-08-24"})

    assert sorted(numbers_of(by_status)) == sorted([processing.payment_no, cleared.payment_no])
    assert numbers_of(by_method) == [cleared.payment_no]
    assert len(by_purpose.data["results"]) == 2
    assert by_type.data["results"] == [], "no credit rows exist — the filter narrows honestly"
    assert len(by_account.data["results"]) == 2
    assert numbers_of(by_confirmation) == [processing.payment_no]
    assert len(by_account_no.data["results"]) == 2
    assert numbers_of(posted_window) == [processing.payment_no]
    # The clearing window catches NEITHER: one cleared Aug 25 (outside), the
    # other has not cleared at all — and "not cleared yet" is not "cleared early".
    assert cleared_window.data["results"] == []


def test_us_pay_004_tc1__the_totals_tie_to_the_current_filter(brazos, marcus):
    """TC-1's "totals row per current filter", as an exact sum of stored rows.

    Σ of NUMERIC(18,6) values is exact — no rounding event is introduced here
    (B4 rounds at finalization and display, and this is neither). The currency
    is the rows' own; it is never assumed.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        a_recorded_payment(brazos, marcus, account, amount=Decimal("100.00"))
        a_recorded_payment(brazos, marcus, account, amount=Decimal("45.50"))

        everything = listed(brazos)
        filtered = listed(brazos, **{"f.status": models.PAYMENT_PROCESSING})

    assert everything.data["totals"]["count"] == 2
    assert everything.data["totals"]["amount"] == "145.500000"
    assert everything.data["totals"]["currency"] == "USD"
    # An empty filter is a real answer: zero rows, and NO money figure — a
    # "$0.00 total" of nothing is a different claim from "nothing matched".
    assert filtered.data["totals"]["count"] == 0
    assert filtered.data["totals"]["amount"] is None
    assert filtered.data["totals"]["currency"] is None


def test_def3207__the_total_is_the_days_CASH_and_a_credit_no_longer_blanks_it(brazos, marcus, dana):
    """`DEF-3207` · `CR-059` CS-35 task 23 — *"or it will not tie to the drawer"*.

    **THE DEFECT, IN ITS OWN FIGURES.** This read used to refuse a money figure
    outright the moment any non-`payment` row was in the filtered set. That was
    unreachable and therefore harmless until `CR-059` task 22 shipped the ability
    to record a credit on 2026-09-02 — from that hour, **a day of $100.00 cash
    and one $25.00 credit answered `amount: null` for the WHOLE list**, so a
    clerk who granted one concession lost the day's takings.

    **WHY EXCLUDING IS SAFE WHERE SUMMING IS NOT, WHICH IS THE WHOLE ARGUMENT.**
    The refusal existed because whether a credit's sign lives on `amount` is
    B2's own O-4 residue and no signed document closes it — a total that MIXED
    one in could be wrong by twice the row. Leaving it out is correct under
    either reading of the sign, so this needs no ruling and invents nothing.

    The excluded row is COUNTED and never summed, for the same reason: the
    screen can say one row was left out without either of us claiming to know
    what it is worth.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        a_recorded_payment(brazos, marcus, account, amount=Decimal("100.00"))
        a_recorded_payment(
            brazos,
            dana,
            account,
            amount=Decimal("25.00"),
            payment_type=models.PAYMENT_TYPE_CREDIT,
            reason_code="goodwill",
        )
        everything = listed(brazos)

    totals = everything.data["totals"]
    # Both rows are still COUNTED — the list above shows two.
    assert totals["count"] == 2
    # The drawer holds 100.00 and the figure ties to it. NOT 125.00, which would
    # be the O-4 guess, and NOT None, which was the defect.
    assert totals["amount"] == "100.000000"
    assert totals["currency"] == "USD"
    assert totals["amount_unavailable"] is None
    # And the row it left out is VISIBLE. A total that quietly covers less than
    # the list above it is worse than one that refuses.
    assert totals["excluded_count"] == 1


def test_def3207__a_filter_holding_only_credits_says_so_rather_than_reading_zero(
    brazos, marcus, dana
):
    """`$0.00` would read as *"we took nothing"*, which is a different claim.

    The same distinction `no_rows` has always drawn, one case along: *"nothing
    matched this filter"* and *"nothing here was cash"* are both true statements
    about an empty cash figure and only one of them is the right one to make.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        a_recorded_payment(
            brazos,
            dana,
            account,
            amount=Decimal("25.00"),
            payment_type=models.PAYMENT_TYPE_CREDIT,
            reason_code="goodwill",
        )
        everything = listed(brazos)

    totals = everything.data["totals"]
    assert totals["count"] == 1
    assert totals["amount"] is None
    assert totals["currency"] is None
    assert totals["amount_unavailable"] == "no_cash_rows"
    assert totals["excluded_count"] == 1


def test_us_pay_004_tc3__the_method_vocabulary_is_the_tenants_live_list(brazos, marcus):
    """BR-PAY-026 / BR-REP-006 — the filter and the Record modal enumerate the
    LIVE method list, never a hardcoded one.

    US-PAY-001 TC-3 is a tenant adding "Bill-pay portal" and using it
    immediately. Both the S33 method FILTER and the S22 method SELECT read this
    one list, so the two can never offer different vocabularies.

    A DEACTIVATED method drops out: IS-1 deactivates rather than deletes, and a
    tenant that retired a method has said stop using it — `record_payment`
    refuses one, so offering it would be a control that always fails.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        an_account(marcus, brazos)
        served = listed(brazos).data["methods"]
        codes = {entry["code"] for entry in served}
        assert {"cash", "check", "card", "ach", "wire", "money_order"} <= codes
        assert all(entry["name"] for entry in served), "the picker shows names, not codes"

        tenancy_models.PaymentMethod.objects.filter(tenant=brazos, code="wire").update(active=False)
        assert "wire" not in {entry["code"] for entry in listed(brazos).data["methods"]}


def test_us_pay_004_tc6__no_write_verb_exists_on_any_payment_path(brazos):
    """BR-PAY-002 / HR-4 / 11b G8 — the ledger mutates nothing, BY DECLARATION.

    There is no PUT, PATCH or DELETE on a payment anywhere in this API: the two
    views declare exactly one verb each, so an undeclared one is refused with
    405 by DRF before any handler body runs. A correction is a NEW reversing row
    (US-PAY-010) — a different story, and one that has no endpoint yet.

    Asserted on the DECLARED verb set rather than over HTTP on purpose: an
    unauthenticated PUT answers 401, because DRF authenticates before it
    dispatches on method, so an HTTP probe would prove the authentication layer
    rather than the method ban. This reads the ban itself.
    """
    assert set(payments_api.payments.cls.http_method_names) == {"get", "options"}
    assert set(payments_api.account_payments.cls.http_method_names) == {"post", "options"}
    # ⚠ AMENDED 2026-08-15 (payments visible-half lane). This assertion used to
    # pin the WHOLE url list to two routes, which made it fail the moment any
    # payments endpoint was added — including read-only ones that carry no write
    # verb at all, which is not what the case is about. It now asserts the BAN
    # itself: no route whose path is a PAYMENT declares a mutating verb, and the
    # money-moving routes that do exist (a write-off request, its approval, a
    # collections run) are their own stories' and are not payment paths.
    payment_routes = {
        pattern.pattern._route: pattern.callback
        for pattern in payments_api.urlpatterns
        if pattern.pattern._route.endswith("payments")
    }
    assert set(payment_routes) == {"payments", "accounts/<str:account_id>/payments"}
    for route, view in payment_routes.items():
        assert not {"put", "patch", "delete"} & set(view.cls.http_method_names), route


@pytest.mark.isolation
def test_us_pay_004_tc7__the_ledger_never_shows_another_tenants_payments(
    brazos, lonestar, marcus, erin
):
    """US-PAY-004 TC-7 — "J. Okafor lists payments → Lone Star Ridge rows only".

    Scoped EXPLICITLY rather than by counting the whole table: on the SQLite
    developer tier there is no RLS to do it, so an unscoped count would see
    Brazos Bend's row and the assertion would be about the wrong thing. The
    DATABASE half of the same law is
    `test_us_pay_001_record_payment.py::…tc7b`, on live PostgreSQL.
    """
    with tenant_ctx(brazos):
        brazos_account = an_account(marcus, brazos)
        pe1_bills(brazos, brazos_account)
        mine = a_recorded_payment(brazos, marcus, brazos_account)

    with tenant_ctx(lonestar):
        theirs = listed(lonestar)

    assert theirs.status_code == 200
    assert theirs.data["results"] == []
    assert theirs.data["totals"]["count"] == 0
    with tenant_ctx(brazos):
        assert numbers_of(listed(brazos)) == [mine.payment_no]


@pytest.mark.isolation
def test_us_pay_001_tc7__recording_into_another_tenants_account_is_refused(
    brazos, lonestar, marcus, erin
):
    """US-PAY-001 TC-7 — a Lone Star Ridge clerk names a Brazos Bend account id.

    The account resolves through customers' own tenant-scoped read and comes
    back empty, so the refusal never reveals whether the id was real (HR-1). On
    PostgreSQL RLS refuses it a second time.
    """
    with tenant_ctx(brazos):
        brazos_account = an_account(marcus, brazos)

    with tenant_ctx(lonestar):
        response = record(lonestar, erin.user, brazos_account, role="system_admin")

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert models.Payment.objects.filter(tenant=lonestar).count() == 0
    assert models.Payment.objects.filter(tenant=brazos).count() == 0


def test_us_pay_004__a_payment_is_listed_whatever_the_bill_it_met(brazos, marcus):
    """A payment that met NO bill still appears — with an empty `applied_to`.

    The row is not conditional on an allocation: BR-PAY-036 accepts money in
    every account state, and BR-PAY-010 carries whatever no bill absorbed. A
    ledger that hid unallocated money would hide exactly the rows a clerk is
    hunting for.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        an_issued_bill(
            brazos,
            account,
            number="BL-2608-018410",
            total=NEW_BILL_TOTAL,
            issued_on=date(2026, 8, 1),
        )
        a_recorded_payment(brazos, marcus, account, amount=OLD_BILL_TOTAL)
        credit = a_recorded_payment(
            brazos, marcus, account, amount=Decimal("5.00"), order="carry_credit"
        )

        rows = {row["payment_no"]: row for row in listed(brazos).data["results"]}

    assert rows[credit.payment_no]["applied_to"] == []
    assert rows[credit.payment_no]["applied_total"] == "0.000000"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-004@0f1a7c3 (sha1[:7] of the four sources this lane was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md — US-PAY-001 + US-PAY-004 — · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 + §2.9 · 04-docs/01-spec/11-api-contracts.md Addendum r2; co-packet US-PAY-001, same four sources)
# generated: 2026-08-11 by story-coder (W4 payments API lane — the two endpoints the payments write path landed without)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see the lane report for the verbatim AttributeError and Resolver404 this whole file failed with before apps/payments/api.py existed
# exceptions: (1) the DATABASE half of isolation (RLS under a non-superuser probe role) is NOT re-asserted here — `tests/test_us_pay_001_record_payment.py::…tc7b` already holds it for both tables and this environment has no live PostgreSQL, so the two cases marked `-m isolation` here are the APP half and run on every tier · (2) a duplicate submit answers 200/created=false rather than 11b G7's 409 — see the TC-6 docstring for why the staff double-click is not one of G7's four enumerated operations
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
