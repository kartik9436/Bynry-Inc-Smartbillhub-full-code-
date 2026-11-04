# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-025 (EP-CWP-06) — portal home: one number, one date, one
#           button. Screen: CWP-022
# Rules:    BR-CWP-093 (nothing empty ever appears) · BR-CWP-095 (one tip per
#           screen, on and in season; no tip ⇒ no slot) · BR-CWP-047 (the
#           balance is re-read, never cached) · BR-CWP-041 (nothing above the
#           issued bill) · CLAUDE.md hard rule 3 (consumption ALWAYS with its
#           unit) · hard rule 2
# Tests:    this file
# Impacts:  apps/portal/selectors.py `home` · seams/billing_seam.py ·
#           seams/payments_seam.py `last_payment` · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-025`'s cases, and the two absences that are the whole story.

⚠ **THE NEGATIVE CASES ARE THE POINT OF THIS SCREEN.** TC-2, TC-3 and TC-5 are
all about something NOT being there: an attention panel with nothing in it, a
tip slot with no tip, a usage tile on an account with no meter. `BR-CWP-093`
says *nothing empty ever appears*, and the difference between a product with
nothing to say today and one that looks broken is exactly these three.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import re

import pytest

from apps.billing import models as billing_models
from apps.portal import selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    enrol_maria,
    switch_on,
)

TODAY = date(2026, 9, 2)
AUGUST = date(2026, 8, 26)
DUE = date(2026, 9, 14)
#: `US-CWP-025` §4 — the figures the story states.
BILL_TOTAL = "142.1800"
USAGE_QUANTITY = Decimal("4820")
USAGE_UNIT = "gal"


class _Principal:
    """The session's own shape, without a database round trip for it."""

    def __init__(self, tenant_id, account_ids):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)
        self.accounts = ()


def a_billed_account(tenant, actor, *, with_usage: bool = True, unit: str | None = USAGE_UNIT):
    """One account with an issued bill, optionally carrying a usage line.

    ⚠ **THE LINE IS WRITTEN THROUGH THE ORM**, the same posture and the same
    reason `an_issued_bill` states: the issue path drags the rating engine and
    the release gate into a test about a READ over issued figures.
    """
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        invoice = an_issued_bill(
            tenant, account, number="BL-2608-0141", total=BILL_TOTAL, issued_on=AUGUST, due_on=DUE
        )
        if with_usage:
            billing_models.InvoiceLine.objects.create(
                tenant=tenant,
                invoice=invoice,
                account=account,
                kind="usage",
                description="Water used",
                quantity=USAGE_QUANTITY,
                unit=unit,
                amount=Decimal("96.4000"),
                period_start=date(2026, 7, 27),
                period_end=date(2026, 8, 26),
            )
    return account


def a_metered_account(tenant, actor, *, unit: str = USAGE_UNIT):
    """One account with an ISSUED bill **and a stated month of usage**.

    ⚠ **THE MONTH IS WRITTEN THROUGH `monthly_usage_service.recompute_account`,
    THE REAL WRITER.** `BR-MET-106` is what the home tile now reads, and a test
    that inserted `MonthlyUsage` rows by hand would assert against its own
    arithmetic instead of the product's. The READING under it is ORM setup, the
    same posture `an_issued_bill` states for the bill.
    """
    from tests.test_us_cwp_usage_helpers import a_read, a_water_meter, state_the_months

    account = a_billed_account(tenant, actor, with_usage=False)
    meter = a_water_meter(tenant, actor, account.unit_id)
    a_read(
        tenant, account, meter["id"], day=date(2026, 8, 31),
        current="153040", consumption=USAGE_QUANTITY, unit=unit,
    )
    state_the_months(tenant, actor, account)
    return account


def read(tenant, account):
    with tenant_context(tenant.id):
        return selectors.home(_Principal(tenant.id, [account.pk]), today=TODAY)


@pytest.mark.django_db
def test_us_cwp_025_tc1_the_balance_and_the_pay_item_lead_the_page(pine_hill, sarah):
    """TC-1 — `$142.18` owing puts *Pay $142.18* in the attention panel."""
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["balances"]["total_owing"] == BILL_TOTAL
    pay = [item for item in view["attention"] if item["kind"] == "pay"]
    assert len(pay) == 1, view["attention"]
    assert pay[0]["amount"] == BILL_TOTAL


@pytest.mark.django_db
def test_us_cwp_025_tc2_an_account_owing_nothing_gets_an_EMPTY_attention_list(
    pine_hill, sarah
):
    """⚠ **AN EMPTY LIST, NOT A LIST OF NOTHINGS.** The screen closes the panel
    up; a panel saying *no items* is the thing `BR-CWP-093` forbids."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["attention"] == []


@pytest.mark.django_db
def test_us_cwp_025_tc3_no_tip_is_live_so_the_slot_is_absent(pine_hill, sarah):
    """`BR-CWP-095`. ⚠ `None`, never an empty object — the difference is
    whether the screen can tell there was a slot at all."""
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["tip"] is None


@pytest.mark.django_db
def test_us_cwp_025_tc7_the_usage_tile_carries_its_unit(pine_hill, sarah):
    """⚠ **HARD RULE 3, ON THE SCREEN THE RULE IS ABOUT.** `4,820` means
    nothing; `4,820 gal` is the whole point of the tile.

    ⚠ **THE TILE MOVED OFF BILL LINES ON 2026-09-04 (PO ruling), SO THIS
    FIXTURE MOVED WITH IT.** It used to write an `InvoiceLine` and read the
    tile back; the tile reads `metering`'s STORED MONTHS now, because a bill
    line has no row for a month nobody read and so could never tell *no use*
    apart from *no reading*. The reading below is the story's own `4,820 gal`
    on 31 August, stated through the real writer.
    """
    switch_on(pine_hill, sarah)
    account = a_metered_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert len(view["usage"]) == 1, view["usage"]
    row = view["usage"][0]
    assert Decimal(row["quantity"]) == USAGE_QUANTITY
    assert row["unit"] == USAGE_UNIT
    assert row["unit"], "a quantity with no unit must never reach a screen"
    #: `BR-MET-144` — the DISPLAY string is the server's, two decimals with
    #: trailing zeros trimmed. `quantity` stays at storage precision
    #: (`DEF-CWP-3770`).
    assert row["quantity_display"] == "4820"


@pytest.mark.django_db
def test_us_cwp_025_a_reading_with_no_unit_is_DROPPED_not_shown_bare(pine_hill, sarah):
    """⚠ **THE ENFORCEMENT HALF OF HARD RULE 3.** A stated month with a quantity
    and no unit is a data problem; showing `4,820` would turn it into a
    customer's wrong conclusion. It is skipped, and the tile closes up."""
    switch_on(pine_hill, sarah)
    account = a_metered_account(pine_hill, sarah, unit="")
    view = read(pine_hill, account)
    assert view["usage"] == []
    assert view["usage_series"] == []


@pytest.mark.django_db
def test_us_cwp_025_tc5_an_account_with_no_measured_service_has_NO_usage_and_no_chart(
    pine_hill, sarah
):
    """TC-5 — a trash-only account. ⚠ **NO EMPTY CHART**: a chart with no bars
    reads as *you used nothing*, which is a different claim from *this is not
    measured*."""
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah, with_usage=False)
    view = read(pine_hill, account)
    assert view["usage"] == []
    assert view["usage_series"] == []
    # …and the rest of the page is still there.
    assert view["last_bill"] is not None


@pytest.mark.django_db
def test_us_cwp_025_the_last_bill_and_the_recent_list_show_ISSUED_bills_only(
    pine_hill, sarah
):
    """`BR-CWP-041` — a draft is the utility's working copy. A customer who saw
    one would ring up about a figure that is going to change."""
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        billing_models.Invoice.objects.create(
            tenant=pine_hill,
            account=account,
            invoice_no="BL-2609-DRAFT",
            status=billing_models.INVOICE_DRAFT,
            service_date=date(2026, 9, 1),
            period_start=date(2026, 8, 27),
            period_end=date(2026, 9, 26),
            due_date=date(2026, 10, 14),
            subtotal=Decimal("999.9900"),
            tax_total=Decimal("0"),
            total=Decimal("999.9900"),
        )
    view = read(pine_hill, account)
    assert view["last_bill"]["number"] == "BL-2608-0141"
    numbers = [row["number"] for row in view["recent_bills"]]
    assert "BL-2609-DRAFT" not in numbers, "a draft bill must not reach a customer"


@pytest.mark.django_db
def test_us_cwp_025_a_new_customer_gets_None_tiles_rather_than_zeroes(pine_hill, sarah):
    """`BR-CWP-093` on the two money tiles. ⚠ `$0.00` says *you paid nothing*;
    an absent tile says *you have not paid yet*, and only one of those is
    true for somebody who joined last week."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["last_bill"] is None
    assert view["last_payment"] is None


@pytest.mark.django_db
def test_us_cwp_025_the_body_carries_no_database_id(pine_hill, sarah):
    """B14 rule 31 — the visible reference is `invoice_no`, the number on the
    paper a customer is holding.

    ⚠ **THIS USED TO BE AN EXACT KEY SET AND IS NOW AN ALLOW-LIST PLUS A SHAPE
    TEST, AND THE CHANGE MAKES IT A STRONGER GUARD RATHER THAN A WEAKER ONE
    (`DEF-CWP-3965`).** An exact set goes red for any addition — `state` and
    `usage`, which `CWP-022`'s signed table needs — while saying nothing about
    whether the addition is an ID. It now names what a bill row may carry AND
    refuses anything shaped like an id, so a lane adding `bill_run_id` fails on
    the rule this test is about instead of on its own arithmetic.
    """
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    allowed = {
        "number",
        "issued_on",
        "due_on",
        "total",
        "currency",
        "period_start",
        "period_end",
        #: `DEF-CWP-3965` — the two right-hand columns of `CWP-022`'s table,
        #: served only for `recent_bills` (`last_bill` is a tile).
        "owing",
        "state",
        "usage",
    }
    for bill in view["recent_bills"] + [view["last_bill"]]:
        assert set(bill) <= allowed, bill
        for key in bill:
            assert key == "id" or not key.endswith("_id"), f"{key} is a database id (B14 rule 31)"
            assert key != "id", "a bill row never carries its own row id (B14 rule 31)"


@pytest.mark.django_db
def test_us_cwp_025_tc6_the_page_never_leaves_the_tenant(pine_hill, oak_ridge, sarah, elena):
    """Hard rule 1 — isolation in the query, not in the screen."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    with tenant_context(oak_ridge.id):
        theirs = set(
            billing_models.Invoice.objects.filter(tenant_id=oak_ridge.id).values_list(
                "invoice_no", flat=True
            )
        )
    numbers = {row["number"] for row in view["recent_bills"]}
    assert not theirs & numbers


@pytest.mark.django_db
def test_def_cwp_3965_the_home_table_carries_its_state_and_its_usage(pine_hill, sarah):
    """`CWP-022`'s table is *Bill / Period / Usage / Amount / Status*.

    The two right-hand columns arrived with `DEF-CWP-3965`; before it the screen
    could draw three of the five and did not draw a table at all.

    ⚠ **THE STATE IS THE ONE `CWP-027` PAINTS FROM** — `_bill_state` — so a home
    page and a bills list cannot disagree about which bill is overdue.
    ⚠ **THE USAGE CARRIES ITS UNIT OR IS NOT SERVED** (hard rule 3).
    """
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["recent_bills"], "the fixture has no issued bill, so this proves nothing"
    for bill in view["recent_bills"]:
        assert bill["state"] in {"paid", "part_paid", "due", "overdue", "corrected"}, bill
        assert isinstance(bill["usage"], list)
        for row in bill["usage"]:
            assert set(row) == {"quantity_display", "unit"}
            assert row["unit"], "a quantity without its unit is never served (hard rule 3)"
    #: The tile is NOT charged for the two extra reads.
    assert "state" not in view["last_bill"]


@pytest.mark.django_db
def test_def_cwp_3965_your_service_states_four_facts_and_says_when_they_vary(pine_hill, sarah):
    """`CWP-022`'s rail panel — *Address / Plan / Billed / Paperless*.

    ⚠ **EACH FACT IS FOLDED ON ITS OWN.** A landlord's accounts share a plan and
    sit at different addresses; a panel that vanished when a set disagreed would
    take the plan with it, and one that showed the first account's address would
    tell a landlord their service is at one building.
    """
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    service = view["service"]
    assert set(service) == {"address", "plan", "billed", "paperless"}
    for name, fact in service.items():
        assert set(fact) == {"value", "varies"}, (name, fact)
        assert isinstance(fact["varies"], bool)
    #: The address is WALKED to `premises` and is a line a customer would
    #: recognise, never a uuid (hard rule 8, B14 rule 31).
    address = service["address"]["value"]
    if address is not None:
        assert not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", str(address)
        ), address
    assert service["paperless"]["value"] in (None, True, False)

@pytest.mark.django_db
def test_cr085_the_account_card_identifies_the_account_and_masks_the_contact(
    pine_hill, sarah
):
    """`CWP-022`'s account card — PO ruling 2026-09-08.

    Verbatim, in order: *"once I login as consumer - 03 Home ... we are not
    displaying account # of Customer nmae - ther eis no identifier"*, then
    *"can you give big account identifier on home screen - name account #,
    service area, Utility services, assets, phone # and email ID, govt ID -
    last 4 digits etc - you can mask these detials"*, then the trim that
    decides the shape: *"just show IDs not details - Equipment ... W-2209,
    8841-C, F-0118 - this is enough + account status"*.

    ⚠ **THE MASK IS THE ASSERTION THAT MATTERS.** The screen never receives a
    full telephone number or e-mail address, so no later edit of a component
    can reveal one. That is a property of the PAYLOAD and can only be proved
    here.

    ⚠ **AND THE GOVERNMENT ID IS ASSERTED ABSENT.** `customers.Contact` holds
    `gov_id_last4`; nothing in the portal reads it, and whether the portal MAY
    is a decision nobody has made. This case fails the day somebody serves one
    without making it.
    """
    switch_on(pine_hill, sarah)
    account = a_billed_account(pine_hill, sarah)
    view = read(pine_hill, account)
    identity = view["identity"]

    assert set(identity) == {
        "name",
        "status",
        "status_class",
        "services",
        "equipment",
        "phone",
        "phone_varies",
        "email",
        "email_varies",
    }
    for name in ("name", "status", "status_class"):
        assert set(identity[name]) == {"value", "varies"}, (name, identity[name])
        assert isinstance(identity[name]["varies"], bool)

    #: The utility's own word for each service, and each named ONCE.
    codes = [row["code"] for row in identity["services"]]
    assert len(codes) == len(set(codes)), codes
    for row in identity["services"]:
        assert set(row) == {"code", "name"}

    #: ⚠ **BARE REFERENCES, AND NEVER A DATABASE ID** (B14 rule 31). Not even
    #: eight characters of one — `DEF-3158` records that as the same breach as
    #: the whole of it.
    for reference in identity["equipment"]:
        assert isinstance(reference, str) and reference
        assert not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", reference
        ), reference

    #: ⚠ **NO FULL CONTACT LEAVES THE SERVER FOR THIS SCREEN.** Four digits of
    #: a telephone number and one letter of a mailbox, which is enough for a
    #: person to recognise their own record and not enough to read over a
    #: shoulder.
    phone = identity["phone"]
    if phone is not None:
        digits = [character for character in phone if character.isdigit()]
        assert len(digits) <= 4, phone
        assert "•" in phone, phone
    email = identity["email"]
    if email is not None:
        assert "•" in email, email
        assert email.index("•") == 1, email

    #: ⚠ **THE ID ON FILE IS NOT SERVED AND MUST NOT APPEAR BY ACCIDENT.**
    text = str(view)
    for forbidden in ("gov_id", "driving_licence", "ssn", "passport"):
        assert forbidden not in text, forbidden


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-025@this-commit (EP-CWP-06 story + BR-CWP-041/093/095 verbatim)
# generated: 2026-09-04 by the CR-068 wave F build lane
# checklist: A✔ B✔ C✔ D✔(api.py home) E=the screen's F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_025_home.py · G81 (no ORM write in selectors or a seam)
# exceptions: the usage chart reads BILL LINES rather than meter reads — metering publishes no per-account consumption read, and composing one in the portal would put billing arithmetic there
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
