# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (S22/S35 Record payment — the allocation choice) ·
#           US-PAY-006 (allocation — the open bills a payment meets)
#           Screens: S22 · S35 (the bill picker + running remainder) · S21
# Change:   CR-059 CS-4, 2026-09-01 — `GET /accounts/{id}/open-bills`, the read
#           OQ-154 ordered built (PO 2026-08-12: *"Build the open-balance
#           read"*).
# Rules:    BR-PAY-001 (the four staff allocation choices) · BR-PAY-010
#           (oldest-invoice-first) · BR-BIL-004 (an issued bill is immutable) ·
#           BR-TEN-042 (one currency per utility) · BR-TEN-080 (storage 6 ·
#           API 4 · display 2) · CLAUDE.md rule 1 · rule 2 · rule 4
# ───────────────────────────────────────────────────────
"""The open-balance read, and the one number it exists to get right.

**THE CASE THIS FILE IS FOR IS `test_cs4_the_open_balance_is_not_the_issued
_total`.** Everything else here is scaffolding around it. `GET /invoices` could
already tell a clerk that `BL-2608-018410` was issued at **247.87**; after a
200.00 payment the bill owes **47.87**, and a picker offering 247.87 aims money
at a figure that is wrong by 200.00 in a way the clerk cannot see. That is
OQ-154, and it is why two of BR-PAY-001's four confirmed staff choices have
rendered DISABLED on two screens since 2026-08-11 with the engine behind them
finished.

THE FIRST CASE IS ABOUT PLUMBING AND NOT ABOUT MONEY, on purpose (hard-won law
2): a view function that exists is not an endpoint until `config/urls.py`
resolves it and a real request survives the middleware, the authentication and
the permission class. **401 means the route exists and asked for a sign-in; 404
means there is no route** — which is what this path answered before this lane.

WHAT IS DELIBERATELY ASSERTED AS ABSENT. `composition` is `null` and not `[]`,
because billing publishes no kind→class map (OQ-128) and a part-paid bill cannot
state one at all (OQ-129) — an empty list would read as a breakdown that came
back all zeros, which is a claim about a customer's tax. The seam's own problem
code travels beside it and is asserted by name.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from core import errors

from apps.payments import api as payments_api
from apps.payments import open_bills

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_us_pay_001_record_payment import (
    CLEARED_AT,
    NEW_BILL_TOTAL,
    OLD_BILL_TOTAL,
    PE2_OUTSTANDING,
    PE2_PAYMENT,
    POSTED_AT,
    an_issued_bill,
    pe1_bills,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def read(tenant, account, *, role="billing_clerk", account_id=None):
    """GET /accounts/{id}/open-bills exactly as the S22 picker calls it."""
    return api_call(
        payments_api.account_open_bills,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        account_id=account_id or str(account.pk),
    )


def a_water_account(actor, tenant):
    """One account of the ISOLATION tenant, which is Water-only.

    `an_account` asks for an electric unit, which Lone Star Ridge does not sell
    — the fixture refuses it by name (`metering.service_not_enabled`). The point
    of the case below is a cross-tenant id, not a service, so the account is
    built on the service that tenant actually has.
    """
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(actor, address_line="77 Ridgeway", services_available=["water"])
    unit = make_unit(actor, premises["id"], label="Unit A", services=["water"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no="A-90001",
    )


def a_payment(actor, account, amount):
    from apps.payments import services

    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=CLEARED_AT,
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )


# ══════════════════════════════════════════════════════════════════════════
# Is it REACHABLE at all? (hard-won law 2)
# ══════════════════════════════════════════════════════════════════════════
def test_cs4_the_route_is_mounted_and_reachable_through_the_whole_stack(brazos):
    """`resolve()` proves the URLconf knows it; a real HTTP call proves a
    request can GET there through tenancy, auth and the permission class."""
    from django.test import Client
    from django.urls import resolve

    account_id = uuid.uuid4()
    assert (
        resolve(f"/api/brazosbend/accounts/{account_id}/open-bills").func
        is payments_api.account_open_bills
    )

    path = f"/api/{brazos.subdomain}/accounts/{account_id}/open-bills"
    response = Client().get(path)
    assert response.status_code == 401, (
        f"GET {path} answered {response.status_code}: a 404 here means the route is still "
        "not reachable, whatever the URLconf says"
    )
    assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# THE CASE THIS LANE EXISTS FOR
# ══════════════════════════════════════════════════════════════════════════
def test_cs4_the_open_balance_is_not_the_issued_total(brazos, marcus):
    """PE-2 · OQ-154 — issued **247.87**, paid 200.00, still owes **47.87**.

    `GET /invoices` serves the first figure. This endpoint serves the third, and
    carries the second so S21's Bills tab can show *"issued 247.87 · still owes
    47.87"* without doing the subtraction itself.
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
        a_payment(marcus.user, account, PE2_PAYMENT)

        response = read(brazos, account)

    assert response.status_code == 200
    body = response.data
    assert body["bill_count"] == 1
    (bill,) = body["bills"]
    assert bill["number"] == "BL-2608-018410"
    # BR-TEN-080: money crosses the wire at FOUR decimal places, as a STRING.
    assert bill["total"] == "247.8700", "the ISSUED total — what GET /invoices serves"
    assert bill["allocated"] == "200.0000"
    assert bill["open_balance"] == "47.8700", "PE-2's own figure; the picker aims at THIS"
    assert Decimal(bill["open_balance"]) == PE2_OUTSTANDING
    # Hard rule 2 — a CHAR(3) code rides WITH every amount, never assumed.
    assert bill["currency"] == "USD"
    assert body["currency"] == "USD"
    assert body["total_open"] == "47.8700"


def test_cs4_two_open_bills_are_listed_oldest_first_and_summed_for_the_header(brazos, marcus):
    """P1's header — *"owes 341.10 across 2 bills"* — over PE-1's own pair.

    45.00 (July) + 247.87 (August) = **292.87**, and the sum is taken over
    exactly the rows served beneath it so the header and the list can never
    disagree. Oldest first is BR-PAY-001's order, which is also the order the
    money will meet them in.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        body = read(brazos, account).data

    assert [row["number"] for row in body["bills"]] == [
        "BL-2607-018311",
        "BL-2608-018410",
    ]
    assert [row["open_balance"] for row in body["bills"]] == ["45.0000", "247.8700"]
    assert body["bill_count"] == 2
    assert body["total_open"] == "292.8700"
    assert Decimal(body["total_open"]) == OLD_BILL_TOTAL + NEW_BILL_TOTAL


def test_cs4_a_settled_bill_is_absent_rather_than_listed_at_zero(brazos, marcus):
    """A settled bill is not an open bill.

    PE-1: a 292.87 cheque settles both. The picker then offers NOTHING to aim
    at, and `total_open` is **0.0000** — which is a measured fact and not an
    absence: this read looked, and the money the clerk is holding will carry as
    account credit. Listing a bill at 0.00 would offer a control that can only
    produce a refusal (`allocation.py`: *"a row means money moved"*).
    """
    from tests.test_us_pay_001_record_payment import PE1_CHECK

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        a_payment(marcus.user, account, PE1_CHECK)

        body = read(brazos, account).data

    assert body["bills"] == []
    assert body["bill_count"] == 0
    assert body["total_open"] == "0.0000"


def test_cs4_the_within_bill_composition_is_null_and_never_an_empty_list(brazos, marcus):
    """Absence and "all four classes are settled" are DIFFERENT facts.

    Billing publishes no kind→class map (OQ-128) and the tenant's fourth class
    lives unpublished in the ledger (BR-PAY-038), so no bill can state its
    breakdown today. `[]` would render as a breakdown that came back all zeros —
    a claim about how much of a customer's tax is still outstanding. The seam's
    problem code is served by name so a screen can group on it.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        body = read(brazos, account).data

    assert [row["composition"] for row in body["bills"]] == [None, None]
    assert "invoice_composition_unavailable" in {problem["code"] for problem in body["problems"]}


# ══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 1 — a cross-tenant id resolves to nobody's bills
# ══════════════════════════════════════════════════════════════════════════
def test_cs4_another_tenants_account_gets_no_bills_and_no_hint_that_it_exists(
    brazos, lonestar, erin
):
    """HR-1 / BR-TEN-003. The refusal names the RULE, never the other tenant.

    It refuses by the same sentence and rule id `POST /accounts/{id}/payments`
    refuses by, deliberately: a picker and the record call that follows it must
    agree on what an account is, or a clerk gets a list of bills for an account
    the payment then bounces off.
    """
    with tenant_ctx(lonestar):
        stranger = a_water_account(erin, lonestar)
        pe1_bills(lonestar, stranger)

    with tenant_ctx(brazos):
        response = read(brazos, stranger)

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-PAY-022"
    # It says the id is not an account OF THIS TENANT — never that it belongs
    # to somebody else, and never a bill number, a customer name or a balance.
    assert "lonestar" not in str(response.data).lower()


def test_cs4_an_unknown_account_id_refuses_rather_than_serving_an_empty_list(brazos):
    """An id that is nobody's must not read as *"this account owes nothing"*.

    Two different facts, and a clerk would act on the second. The seam's own
    posture, one layer up.
    """
    with tenant_ctx(brazos):
        response = api_call(
            payments_api.account_open_bills,
            "get",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            account_id=str(uuid.uuid4()),
        )

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-PAY-022"


def test_cs4_the_read_writes_nothing_and_reads_no_clock(brazos, marcus):
    """It is a READ (CLAUDE.md rule 4) and it takes no date (BR-TEN-043).

    The absence of a clock is asserted directly as well as behaviourally: one
    added later would be invisible to a test that only checks the values it was
    handed. `open_bill_position` takes exactly one argument, and it is the
    account.
    """
    import inspect

    from apps.payments import models

    signature = inspect.signature(open_bills.open_bill_position)
    assert list(signature.parameters) == ["account_id"]
    source = inspect.getsource(open_bills)
    for clock in ("datetime.now", "date.today", "timezone.now"):
        assert clock not in source, f"{clock} in a read that is handed no date (BR-TEN-043)"

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        before = models.Payment.objects.count(), models.Allocation.objects.count()
        read(brazos, account)
        assert (models.Payment.objects.count(), models.Allocation.objects.count()) == before


def test_cs4_an_executive_may_look_and_the_route_declares_no_write_verb(brazos, marcus):
    """A4 `payments_record`: Executive is VIEW, and this is a view.

    The route declares GET only, so a forged PUT/PATCH/DELETE is refused by the
    router with 405 before any handler runs (BR-PAY-002 / hard rule 4).
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        response = read(brazos, account, role="executive")

    assert response.status_code == 200
    assert set(payments_api.account_open_bills.cls.http_method_names) >= {"get"}
    assert "post" not in payments_api.account_open_bills.cls().allowed_methods


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@08c9bfec · US-PAY-006@08c9bfec — CR-059 CS-4 (sha1[:8] of the four sources concatenated in order: 12-governance/11-change-requests.md §8 CS-4 · §10 P1 · §11 task 11 · 12-governance/01-open-questions.md OQ-154 CLOSED · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-001/010/012)
# generated: 2026-09-01 by the CR-059 task 11 lane (CS-4)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every case was driven RED first (hard-won law 7) — before the route existed the mount case failed on `AttributeError: module 'apps.payments.api' has no attribute 'account_open_bills'` and the HTTP probe on `assert 404 == 401`; the open-vs-issued case failed on the absent `open_balance` key
# exceptions: (1) NO BUDGET-BILLING CASE IS ASSERTED HERE and that is DEF-2416, not an omission: the seam measures every bill at `invoice.total` (WE-8 totals 292.87 and asks 242.00), the fix moves money logic on the allocation path, and CR-059 CS-4 excludes that in terms. A test written now would pin the WRONG figure and make the fix look like a regression · (2) THE SCREEN IS NOT TESTED — CR-059 task 12 owns S22/S35's picker and the deletion of the on-screen refusal text; this file proves the endpoint only
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
