# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-050 (EP-CWP-09) — collecting a connection fee. Screen:
#           CWP-050 (blueprint `P36`)
# Rules:    BR-CWP-058 (the consequence is shown before the commit) ·
#           BR-CWP-056 (the Pay control appears disabled until rails) ·
#           BR-CUS-090 (the quote, what was taken, and the difference) ·
#           BR-CWP-010 · BR-CWP-093 · CLAUDE.md hard rule 2
# Ruling:   PO 2026-09-05 (`OQ-CWP-1600`), verbatim: *"we have reconnect fees in
#           charge code, plan will tell you how much to charge, plan is attached
#           to unit and unit is attached to account"* — ⚠ **a hardcoded fee or
#           deposit figure anywhere is now a defect**, and this file is where
#           the connection half of that is proved.
# Cases:    TC-1 the four rows · TC-2 ⚠ the arithmetic · TC-3 the waived row ·
#           TC-4 the deposit that stays on the first bill · TC-5 no rails ·
#           TC-6 no partial payment · TC-7 isolation · TC-8 not yet approved
# ───────────────────────────────────────────────────────
"""**EVERY FIGURE ON THIS SCREEN IS READ, AND THE TEST THAT MATTERS ASSERTS THAT
RATHER THAN ASSERTING THE NUMBER.**

`US-CWP-050` §4 quotes `$185.00`, `$150.00`, `$150.00` and `$25.00`, and it
would be trivial — and wrong — to satisfy this file with four constants. The PO
ruled on 2026-09-05 that a fee is a **charge code** and its amount comes from
the **plan**, reached by walking **unit → plan**. So:

  * the two *before we start* lines are `service_request_fees` rows, quoted from
    the tenant's own charge catalogue by a clerk;
  * the deposit is `rating.PlanDepositRule.amount`, read through
    `rating_seam.deposit` — **the same function `CWP-008` quotes from**, which is
    what `§7`'s *"must equal the figure quoted on `CWP-008`"* asks for, and
    `test_the_deposit_is_the_same_read_cwp_008_quotes_from` asserts it by
    reading both rather than by writing `150` twice.

⚠ **AND A DEPOSIT NOBODY HAS PRICED IS AN ABSENCE, NEVER `$0.00`** — the posture
`selectors.DEPOSIT_NOT_PRICED` already set on `CWP-057` one screen along. A zero
on this screen tells an applicant a deposit costs nothing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import models as customers_models, service_request_service
from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line
from apps.portal import paying
from apps.portal.seams import customers_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    brand_fully,
    elm_street_account,
    seed_addresses_for,
    switch_on,
)

#: `US-CWP-050` §4 — the story's own fixture, `SR-26-0061`.
REFERENCE = "SR-26-0061"
NEW_CONNECTION = Decimal("185.00")
METER_INSTALL = Decimal("150.00")
SET_UP = Decimal("25.00")
#: ⚠ 185.00 + 150.00, and the waived 25.00 is in NEITHER total.
TO_PAY_NOW = "335.0000"
ON_FIRST_BILL = "150.0000"
APPLICANT_PHONE = "512-555-0161"


@pytest.fixture()
def pine_addresses(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


def _unit_at(tenant, address_line):
    from apps.metering import models as metering_models

    with tenant_context(tenant.id):
        return (
            metering_models.Unit.objects.filter(
                tenant_id=tenant.id, premises__address_line=address_line
            )
            .order_by("id")
            .first()
        )


def _approved_request(tenant, actor, *, unit, state=None, waive_the_set_up=True):
    """`SR-26-0061` — approved, with three quoted lines and one of them waived.

    ⚠ **THE LINES GO IN THROUGH `add_fee_line`, THE PUBLISHED DOOR**, so this
    fixture proves nothing about how a fee comes to exist and everything about
    how it READS.
    """
    with tenant_context(tenant.id):
        request = customers_models.ServiceRequest.objects.create(
            tenant=tenant,
            request_no=REFERENCE,
            state=state or customers_models.ServiceRequest.APPROVED,
            address_as_given="31 Palm Ct, Austin TX 78702",
            resolved_unit_id=unit.id if unit is not None else None,
            resolved_premises_id=unit.premises_id if unit is not None else None,
            # ⚠ **THE PHONE AND THE CHANNEL ARE HOW `my_requests` FINDS IT**
            # (`BR-CWP-010`, and `OQ-CWP-1680` records why a phone stands in for
            # an account link that has no column). A fixture setting neither
            # would be building a request the product cannot reach.
            channel=customers_seam.CHANNEL_CUSTOMER_PORTAL,
            applicant_phone=APPLICANT_PHONE,
            fee_timing="collect_now",
            fee_currency="USD",
        )
        quote_fee(
            actor,
            request.id,
            charge_code="CONN",
            unit_amount=NEW_CONNECTION,
            description="New connection",
        )
        quote_fee(
            actor,
            request.id,
            charge_code="CC-METERT",
            unit_amount=METER_INSTALL,
            description="Meter installation",
        )
        set_up = quote_fee(
            actor,
            request.id,
            charge_code="CC-REQFEE",
            unit_amount=SET_UP,
            description="Account set-up",
        )
        if waive_the_set_up:
            service_request_service.waive_fee_line(
                actor, set_up.id, reason="first application at this address"
            )
    return request


def fees(tenant, *, phones=None):
    with tenant_context(tenant.id):
        return paying.fees_position(tenant.id, phones=phones or [APPLICANT_PHONE])


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 / TC-3 · THE FOUR ROWS, AND THE WAIVED ONE IS STILL THERE
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc1_tc3_four_rows_and_the_waived_one_is_listed_not_deleted(pine_addresses, sarah):
    """⚠ **A WAIVED FEE STAYS ON THE LIST, STRUCK THROUGH.**

    The record keeps a WAIVER rather than deleting the line, *"which is what
    lets a customer see they were let off rather than wonder whether they were
    quoted correctly"*.
    """
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(pine_addresses, sarah, unit=unit)

    body = fees(pine_addresses)

    assert body["any"] is True
    assert body["reference"] == REFERENCE  # a human reference, never an id
    assert [row["what"] for row in body["lines"]] == [
        "New connection",
        "Meter installation",
        "Account set-up",
        "Security deposit",
    ]
    set_up = body["lines"][2]
    assert set_up["waived"] is True
    assert set_up["amount"] == "25.0000", "still listed with its figure, struck through"
    deposit = body["lines"][3]
    assert deposit["when"] == paying.WHEN_FIRST_BILL
    assert deposit["amount"] == ON_FIRST_BILL


# ═══════════════════════════════════════════════════════════════════════════
# ⚠ TC-2 · THE ARITHMETIC
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc2_to_pay_now_is_335_and_the_waived_25_is_in_neither_total(pine_addresses, sarah):
    """`$185.00 + $150.00` = **`$335.00`**; *on your first bill* = `$150.00`;
    the waived `$25.00` is in **neither**."""
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(pine_addresses, sarah, unit=unit)

    body = fees(pine_addresses)

    assert body["to_pay_now"]["amount"] == TO_PAY_NOW
    assert body["to_pay_now"]["display"] == "$335.00"  # hard rule 2 — display 2
    assert body["on_first_bill"]["amount"] == ON_FIRST_BILL
    assert body["on_first_bill"]["display"] == "$150.00"


@pytest.mark.django_db
def test_the_deposit_is_the_same_read_cwp_008_quotes_from(pine_addresses, sarah):
    """§7 — *"This must equal the figure quoted on `CWP-008` before the customer
    applied."*

    ⚠ **ASSERTED BY READING BOTH, NOT BY WRITING `150` TWICE.** A disagreement
    between the quote and the invoice is the defect both stories test for, and a
    test carrying its own constant could not see one.
    """
    from apps.portal import availability

    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(pine_addresses, sarah, unit=unit)

    with tenant_context(pine_addresses.id):
        quoted = availability.availability(pine_addresses.id, "31 Palm Ct")
    body = fees(pine_addresses)

    assert body["on_first_bill"]["amount"] == quoted["if_you_apply"]["on_first_bill"]["amount"]


@pytest.mark.django_db
def test_a_deposit_nobody_has_priced_is_an_absence_and_never_zero(pine_addresses, sarah):
    """⚠ **`$0.00` WOULD TELL AN APPLICANT A DEPOSIT COSTS NOTHING.**

    `selectors.DEPOSIT_NOT_PRICED`'s posture, one screen along: a total that
    silently omits a figure is a total the customer discovers is wrong at the
    counter, so the row is absent and the gap is NAMED.
    """
    from apps.rating import models as rating_models

    unit = _unit_at(pine_addresses, "31 Palm Ct")
    with tenant_context(pine_addresses.id):
        rating_models.PlanDepositRule.objects.all().delete()
    _approved_request(pine_addresses, sarah, unit=unit)

    body = fees(pine_addresses)

    assert [row["what"] for row in body["lines"]] == [
        "New connection",
        "Meter installation",
        "Account set-up",
    ]
    assert body["on_first_bill"] is None
    assert any(one["code"] == paying.DEPOSIT_NOT_PRICED for one in body["problems"])
    assert "0.00" != str(body["on_first_bill"])


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 · PAYING THE 335.00 LEAVES THE DEPOSIT ON THE FIRST BILL
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc4_collecting_the_335_leaves_the_150_deposit_due_on_the_first_bill(pine_addresses, sarah):
    """⚠ **THE DEPOSIT IS NOT TAKEN NOW.** It lands on the first bill, and
    collecting the fees must not quietly sweep it up."""
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    request = _approved_request(pine_addresses, sarah, unit=unit)

    with tenant_context(pine_addresses.id):
        service_request_service.collect_fee(
            sarah,
            request.id,
            amount=Decimal("335.00"),
            method="cash",
            receipt_no="RCP-26-4471",
        )

    body = fees(pine_addresses)

    assert body["to_pay_now"]["amount"] == "0.0000", "the fees are settled"
    assert (
        body["on_first_bill"]["amount"] == ON_FIRST_BILL
    ), "the deposit followed the fees out of the door — it belongs on the first bill"


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 / TC-6 · RAILS ABSENT, AND NO PARTIAL AMOUNT
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc5_tc6_the_control_is_held_and_the_table_is_fully_readable(pine_addresses, sarah):
    """The control is disabled with its reason and the fee table is fully
    readable (TC-5). ⚠ **NO PART AMOUNT TRAVELS** (TC-6): fees are collected in
    full before work starts, so the payload offers ONE figure and no minimum,
    no instalment and nothing a screen could turn into an amount box."""
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(pine_addresses, sarah, unit=unit)

    body = fees(pine_addresses)

    assert body["available"] is False
    assert body["held_reason"] == paying.HELD_NO_FEE_PAYMENT_PATH
    assert len(body["lines"]) == 4
    for key in ("minimum", "part_payment", "instalments", "amount_options"):
        assert key not in body, f"a partial fee payment is expressible through {key!r}"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 · TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc7_an_oak_ridge_session_never_sees_pine_hills_fees(
    pine_addresses, sarah, oak_ridge, elena
):
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(pine_addresses, sarah, unit=unit)

    body = fees(oak_ridge)

    assert body["any"] is False
    assert "185" not in str(body) and "335" not in str(body)


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 · A REQUEST NOT YET APPROVED
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc8_fees_are_quoted_after_approval_and_not_before(pine_addresses, sarah):
    """⚠ **THE QUOTE DOES NOT REACH THE APPLICANT BEFORE A CLERK APPROVES.**

    *"Approving creates real service and real charges, so the decision is made
    deliberately"* (`B19` §12.3). A submitted request with three priced lines
    answers `any: false` — not a table with a held button over it.
    """
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(
        pine_addresses,
        sarah,
        unit=unit,
        state=customers_models.ServiceRequest.SUBMITTED,
    )

    body = fees(pine_addresses)

    assert body["any"] is False
    assert body["lines"] == []
    assert "185" not in str(body)


# ═══════════════════════════════════════════════════════════════════════════
# THE HOLD'S OWN EXPIRY TEST (hard-won law 2's mirror)
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_the_pay_hold_expires_when_the_portal_gains_a_payment_write(pine_addresses, sarah):
    """⚠ **THE HOLD'S OWN EXPIRY TEST, RE-AIMED AFTER IT FIRED CORRECTLY.**

    Its first form asserted that `apps/payments/gateway.py` did not exist, and
    **it went RED within the afternoon** — lane B landed a real gateway for
    `US-CWP-045`. That is the mechanism working, and the honest response was to
    ask whether the refusal was still true rather than to move the assertion
    until it passed.

    **It is still true and it was worded wrongly.** A charging path exists; a
    way for a CUSTOMER TO PAY A FEE does not. `service_request_fees` is a quote
    that never posts to the ledger (B18 §4.6), `collect_fee` is a counter action
    gated to Admin or Billing Clerk, and `write_points.WRITE_POINTS`'s `payment`
    row still carries `function=None` — **this product's own machine-readable
    statement that the portal writes no payment at all**, and the thing that
    must change before *Pay $335.00* can do anything.

    ⚠ **A GATEWAY EXISTING WAS TOO COARSE A SENTINEL**, which is the lesson: a
    hold's expiry test has to watch the thing that makes THAT refusal false, not
    the nearest thing that is easy to check.
    """
    from apps.portal import write_points

    payment = next(one for one in write_points.WRITE_POINTS if one.kind == "payment")
    assert payment.function is None, (
        "the portal writes payments now: CWP-050's Pay control "
        "(paying.HELD_NO_FEE_PAYMENT_PATH and its catalogue sentence) must be "
        "re-examined — a fee is a QUOTE that posts to no ledger, so paying one "
        "is a decision about where that money is recorded and not a wiring job"
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE WIRE — hard-won law 2, *built is not wired*
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_fees_endpoint_answers_and_never_lets_a_browser_cache_it(pine_addresses, sarah):
    """`GET fees` — 200, `$335.00`, and `no-store`.

    ⚠ **THE PHONE THE SESSION HOLDS IS WHAT FINDS THE REQUEST** (`BR-CWP-010`),
    so the fixture puts the applicant\'s number on the account this login proves
    it holds — which is exactly what every portal write already does.
    """
    from django.test import Client

    from apps.customers import models as cust
    from tests.test_us_cwp_helpers import MARIA_EMAIL, MARIA_PASSWORD, enrol_maria

    enrol_maria(pine_addresses, sarah)
    account = elm_street_account(pine_addresses, sarah)
    with tenant_context(pine_addresses.id):
        # ⚠ `is_primary=True` is load-bearing: `contact_phones` filters on it,
        # so a secondary contact's number would find no request at all.
        cust.Contact.objects.update_or_create(
            tenant=pine_addresses,
            account=account,
            is_primary=True,
            defaults={"full_name": "Maria Alvarez", "phone": APPLICANT_PHONE},
        )
    unit = _unit_at(pine_addresses, "31 Palm Ct")
    _approved_request(pine_addresses, sarah, unit=unit)

    client = Client()
    client.post(
        f"/api/{pine_addresses.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(f"/api/{pine_addresses.subdomain}/portal/fees")

    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]
    body = response.json()
    assert body["any"] is True
    assert body["to_pay_now"]["display"] == "$335.00"
    assert body["reference"] == REFERENCE
    # ⚠ B14 rule 31 — the reference is the identity and no row id travels.
    assert "id" not in body


@pytest.mark.django_db
def test_the_fees_route_offers_no_way_to_pay(pine_addresses, sarah):
    """⚠ **`US-CWP-050` TC-5/TC-6 AT THE EDGE.** No gateway exists (`CR-068`
    R2), so there is no POST to take money and no route a part payment could be
    sent to. The control on the screen is disabled and carries its reason."""
    from django.test import Client

    from apps.portal import api as portal_api
    from tests.test_us_cwp_helpers import MARIA_EMAIL, MARIA_PASSWORD, enrol_maria

    enrol_maria(pine_addresses, sarah)
    client = Client()
    client.post(
        f"/api/{pine_addresses.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    posted = client.post(
        f"/api/{pine_addresses.subdomain}/portal/fees",
        data={"amount": "100.00"},
        content_type="application/json",
    )
    assert posted.status_code == 405, posted.content

    routes = [str(one.pattern) for one in portal_api.urlpatterns]
    assert not any("fees/pay" in one or "fees/collect" in one for one in routes)
