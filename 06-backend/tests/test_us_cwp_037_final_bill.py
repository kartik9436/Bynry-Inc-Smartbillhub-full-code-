# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-037 (EP-CWP-07) — *your final bill, where the deposit comes
#           back.* Screen: CWP-032
# Rules:    BR-CWP-048 (a negative final balance is a REFUND, never a carried
#           credit) · BR-CWP-049 (the deposit and its accrued interest settle
#           here) · BR-BIL-013 (the deposit applies FIRST, then exactly one
#           path) · BR-CUS-057 (the interest arithmetic, finance-signed) ·
#           BR-CWP-010 · CLAUDE.md hard rule 2
# Golden:   ❄️ GT-61 is the frozen deposit-interest chain. Nothing here
#           recomputes it — `customers.selectors.deposit_interest_accrued` is
#           read, through `billing.final_bill.deposit_credit_for`.
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `final_bill_for` ·
#           `closing_reading_for` · apps/portal/selectors.py `final_bill`
# ───────────────────────────────────────────────────────
"""`US-CWP-037`'s cases — and the one figure two screens must agree on.

⚠ **THE FINAL BILL IS WHERE A DEPOSIT COMES BACK, AND A DEPOSIT IS MONEY.**
`apps.billing.final_bill.settle_final_bill` settles a closing account for a
CLERK; this screen calls the same function. `US-CWP-037` §7 says why in as many
words: *"the figures must agree with `US-CWP-031`'s deposit panel — a
disagreement between the two is the defect both stories test for."* So the
worked case below is asserted twice, once through the settlement and once
through `CWP-065`'s own read, on the same account in the same test.

    service `$63.40` − deposit `$150.00` − interest `$3.20` = **−$89.80**
    → *we owe you `$89.80`*, raised as a REFUND and never as a credit.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.test import Client

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.portal import selectors as portal_selectors
from apps.portal.seams import billing_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-037` §4's own figures.
MOVED_OUT_ON = date(2026, 9, 17)
PERIOD_START = date(2026, 9, 1)
SERVICE_CHARGES = Decimal("63.4000")
DEPOSIT_HELD = Decimal("150.0000")
DEPOSIT_TAKEN_ON = date(2021, 3, 4)


class _Principal:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


def _a_final_bill(tenant, account, *, total=SERVICE_CHARGES, number="BL-2609-0163"):
    """One ISSUED bill typed `final`, in the shape the settlement meets it.

    ⚠ **THROUGH THE ORM AND NOT THROUGH THE BILL RUN**, the shape
    `test_us_cwp_helpers.an_issued_bill` already established and states its own
    reason for: the issue path drags the rating engine, the GL stamp and the
    release gate into a test about what happens to a bill AFTER it exists.
    `bill_type`, `total`, `period_end` and `status` are the only issue-time
    facts this read consults.
    """
    with tenant_context(tenant.id):
        return billing_models.Invoice.objects.create(
            tenant=tenant,
            account=account,
            invoice_no=number,
            status=billing_models.INVOICE_ISSUED,
            bill_type=billing_seam.BILL_TYPE_FINAL,
            service_date=MOVED_OUT_ON,
            period_start=PERIOD_START,
            # BR-CUS-056 — the outgoing account pays the move DAY, so the
            # period ends ON it and the screen reads the move-out date here.
            period_end=MOVED_OUT_ON,
            due_date=date(2026, 10, 2),
            subtotal=total,
            tax_total=Decimal("0"),
            total=total,
            currency="USD",
            issued_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        )


def _hold_a_deposit(tenant, account, *, amount=DEPOSIT_HELD, on=DEPOSIT_TAKEN_ON):
    """Put a deposit on the account and hand back a FRESH row.

    ⚠ **THE REFRESH IS LOAD-BEARING AND ITS ABSENCE COST A CONFUSING HOUR.**
    `account_summary` reads `deposit_on_file` off the ROW IT IS PASSED, while
    `final_bill` reaches through `deposit_credit_for`, which re-queries. So a
    test that kept the stale object saw the settlement find a deposit and the
    `CWP-065` panel find none — which looks exactly like the two screens
    disagreeing, the very defect TC-5 exists to catch, and was neither.
    """
    with tenant_context(tenant.id):
        customers_models.Account.objects.filter(pk=account.pk).update(
            deposit_on_file=amount, deposit_received_on=on
        )
        return customers_models.Account.objects.get(pk=account.pk)


def _read(tenant, account):
    with tenant_context(tenant.id):
        return portal_selectors.final_bill(
            _Principal(tenant.id), account, today=date(2026, 9, 18)
        )


@pytest.mark.django_db
def test_us_cwp_037_tc1_tc2_the_settlement_arithmetic(pine_hill, sarah):
    """TC-1 / TC-2 — `$63.40 − $150.00 − $3.20 = −$89.80`.

    ⚠ **THE INTEREST IS WHATEVER THE SIGNED ENGINE SAYS AND IS NOT TYPED HERE.**
    `BR-CUS-057`'s accrual depends on the tenant's rate and the months held, so
    the assertion is on the ARITHMETIC — service minus principal minus interest
    equals the remainder — and on the direction. A literal `$3.20` would be this
    test asserting the engine's answer back at it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account)
    view = _read(pine_hill, account)
    bill = view["bill"]
    assert bill is not None
    assert bill["service_charges"] == "63.4000"
    assert bill["deposit"]["held"] == "150.0000"
    interest = Decimal(bill["deposit"]["interest"])
    remainder = Decimal(bill["remainder"])
    assert remainder == SERVICE_CHARGES - DEPOSIT_HELD - interest
    # ⚠ NEGATIVE IS MONEY OWED BACK, and the sign is on the wire.
    assert remainder < 0


@pytest.mark.django_db
def test_us_cwp_037_tc4_a_negative_remainder_is_a_REFUND(pine_hill, sarah):
    """TC-4 · negative — the engine's own path, not a reading of the sign.

    `BR-CWP-048`: a negative final balance is a refund and never a carried
    credit, because there is no next bill to carry it to. `settle` chooses
    `refund` automatically — *"nobody chooses whether to give back money that is
    not theirs"* — and this asserts the portal serves that word.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account)
    bill = _read(pine_hill, account)["bill"]
    assert bill["path"] == "refund"
    assert bill["path_is_automatic"] is True


@pytest.mark.django_db
def test_us_cwp_037_tc3_service_exceeding_the_deposit_reads_as_OWED(pine_hill, sarah):
    """TC-3 · negative — a final bill where service EXCEEDS the deposit.

    The remainder is positive, the path is a staff choice rather than an
    automatic refund, and nothing about the body says *we owe you*.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account, total=Decimal("289.1000"))
    bill = _read(pine_hill, account)["bill"]
    assert Decimal(bill["remainder"]) > 0
    assert bill["path"] != "refund"


@pytest.mark.django_db
def test_us_cwp_037_tc5_the_deposit_figures_match_cwp_065_exactly(pine_hill, sarah):
    """TC-5 — ⚠ **THE DEFECT BOTH STORIES EXIST TO CATCH.**

    `CWP-032` reads the deposit through `billing.final_bill.deposit_credit_for`
    and `CWP-065` through `customers_seam.deposit_interest`; both resolve ONE
    implementation of each figure, so the two screens agree by construction.
    This asserts it rather than trusting it — a lane that later gave either
    screen its own accrual would go red here.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account)
    final = _read(pine_hill, account)["bill"]["deposit"]
    with tenant_context(pine_hill.id):
        summary = portal_selectors.account_summary(
            pine_hill.id, account, as_of=date(2026, 9, 18)
        )
    panel = summary["deposit"]
    assert panel is not None
    assert Decimal(final["held"]) == Decimal(panel["held"])
    assert Decimal(final["interest"]) == Decimal(panel["interest"])
    assert final["taken_on"] == panel["taken_on"] == DEPOSIT_TAKEN_ON.isoformat()


@pytest.mark.django_db
def test_us_cwp_037_tc6_an_account_with_no_deposit_has_no_deposit_at_all(
    pine_hill, sarah
):
    """TC-6 · negative — the deposit is ABSENT, not `$0.00`.

    `$0.00` held reads as *we took nothing from you*, which is a different
    sentence from *there is nothing here* — the same line `CWP-065`'s panel
    already draws.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _a_final_bill(pine_hill, account)
    bill = _read(pine_hill, account)["bill"]
    assert bill["deposit"] is None
    assert Decimal(bill["remainder"]) == SERVICE_CHARGES


@pytest.mark.django_db
def test_us_cwp_037_an_account_that_is_not_leaving_has_no_final_bill(pine_hill, sarah):
    """`bill: None` — never an empty settlement, which a screen would draw as
    *we owe you `$0.00`* over an account whose service is not ending."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    view = _read(pine_hill, account)
    assert view["bill"] is None
    assert view["closing_reading"] is None


@pytest.mark.django_db
def test_us_cwp_037_an_ordinary_cycle_bill_is_not_a_final_bill(pine_hill, sarah):
    """⚠ **THE `bill_type` FILTER IS THE WHOLE GUARD.** `settle_final_bill`
    refuses a bill typed anything else by name — *"applying the deposit to an
    ordinary cycle bill would credit the customer twice over the tenancy"* — so
    a read that found one would be asking for a refusal on every account."""
    from tests.test_us_cwp_helpers import an_issued_bill

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    an_issued_bill(
        pine_hill, account, number="BL-2608-0141", total="142.1800", issued_on=date(2026, 8, 30)
    )
    assert _read(pine_hill, account)["bill"] is None


@pytest.mark.django_db
def test_us_cwp_037_tc9_the_query_route_closes_once_the_account_settles(
    pine_hill, sarah
):
    """TC-9 · negative — once settled the route is gone AND a reason is given.

    A settlement with an automatic path is settled the moment it is computed
    (`Settlement.settled`), which is the honest reading of *the account closes*:
    the refund is raised, and a correction from here is a slower business.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account)
    view = _read(pine_hill, account)
    # This account settles automatically as a refund, so the route is closed.
    assert view["bill"]["settled"] is True
    assert view["query_reading_open"] is False
    assert view["query_reading_closed_reason"] == "settled_correction_is_slower"


@pytest.mark.django_db
def test_us_cwp_037_the_query_route_is_open_while_a_path_is_still_a_staff_choice(
    pine_hill, sarah
):
    """The other side of TC-9: a remainder the staff must still choose a path
    for is NOT settled, so the customer's last chance to query is still open."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account, total=Decimal("289.1000"))
    view = _read(pine_hill, account)
    assert view["bill"]["settled"] is False
    assert view["query_reading_open"] is True
    assert view["query_reading_closed_reason"] is None


@pytest.mark.django_db
def test_us_cwp_037_the_closing_reading_is_the_one_on_or_before_the_move_day(
    pine_hill, sarah
):
    """TC-8 — the reading the bill was cut on, chosen out of the list `CWP-034`
    already shows.

    ⚠ **A READING TAKEN AFTER THE MOVE DAY BELONGS TO WHOEVER MOVED IN**, so it
    is never the closing one — `BR-CUS-056` bills THROUGH the move day.
    """
    rows = [
        {"taken_on": "2026-09-25", "reading_display": "155,900"},
        {"taken_on": "2026-09-17", "reading_display": "154,310"},
        {"taken_on": "2026-09-01", "reading_display": "153,040"},
    ]
    chosen = billing_seam.closing_reading_for(rows, moved_out_on=MOVED_OUT_ON)
    assert chosen["reading_display"] == "154,310"
    # With no move-out date there is no closing reading to choose.
    assert billing_seam.closing_reading_for(rows, moved_out_on=None) is None


@pytest.mark.django_db
def test_us_cwp_037_tc7_another_utilitys_account_is_refused(pine_hill, sarah):
    """TC-7 · tenant isolation — `BR-CWP-010`, both halves in the query. An
    account outside the session's set answers the same 404 as one that does not
    exist, so the set cannot be enumerated."""
    import uuid

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    refused = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{uuid.uuid4()}/final-bill"
    )
    assert refused.status_code == 404, refused.content


@pytest.mark.django_db
def test_us_cwp_037_the_final_bill_is_never_cached(pine_hill, sarah):
    """`BR-CWP-047` — the body carries a deposit, a settlement and a closing
    meter reading."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    account = _hold_a_deposit(pine_hill, account)
    _a_final_bill(pine_hill, account)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/final-bill"
    )
    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]
    body = response.json()
    assert body["bill"]["service_charges"] == "63.4000"
    # ⚠ B14 rule 31 — no row id crosses this wire; the handle is the number.
    assert body["bill"]["number"] == "BL-2609-0163"
    assert "id" not in body["bill"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-037@d9d2f5f3 (EP-CWP-07)
# generated: 2026-09-04 by the CR-068 ending lane
# checklist: A✔ B✔ C✔ D✔(api.final_bill) E✔(portal/bills/FinalBill.tsx) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_037_final_bill.py · G81 · G84 · G96 · G82
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
