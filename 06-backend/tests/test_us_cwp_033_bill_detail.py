# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-033 (EP-CWP-07) — one bill, line by line, grouped by
#           service, every unit named. Screen: CWP-028
# Rules:    BR-CWP-044 (grouped by service; every usage line carries its unit) ·
#           BR-CWP-041 (nothing above the issued bill) · BR-CWP-071 (the
#           readings behind the bill show HOW they were taken) · BR-CWP-010
#           (both halves in the QUERY) · B14 rule 31 (no database id is a
#           visible value) · CLAUDE.md hard rule 2 (4 dp stored, 2 dp
#           displayed) · hard rule 3 (a quantity always carries its unit) · B4
#           (round only at display)
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `bill_detail_for` ·
#           apps/portal/seams/metering_seam.py `reads_behind_bill` ·
#           apps/portal/api.py `bill_detail`
# ───────────────────────────────────────────────────────
"""`US-CWP-033`'s cases — and the one the whole screen exists for.

⚠ **TC-2 IS THE STORY.** *"a customer adding up the lines must reach the
total"*, and the story's own words for what happens otherwise are *"a penny of
disagreement here is a support call"*. So the arithmetic is asserted **on the
displayed figures** — the 2dp strings the screen prints — and never on the 4dp
stored ones, because four stored lines can sum to the stored total and still
print a column that is a cent out. That is the exact failure B4's 2026-08-11
ruling names, and `billing.selectors._charges_by_service` takes the same
reading of it.

Worked, and these are the story's own numbers:

    18.50 + 17.80 + 34.12 + 35.67 + 22.00        = 128.09   (before tax)
    128.09 + 5.42 + 8.67                          = 142.18   (the total)

⚠ **THE SEAM CALLS THE STAFF READ AND THAT IS WHAT MAKES THE FIGURES AGREE.**
`billing.selectors.invoice_detail` is `S30`'s own read (PO 2026-09-04, and the
portal reuse map's row for this screen). Nothing in the portal adds a bill up.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.portal.seams import billing_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

TODAY = date(2026, 9, 2)
AUGUST = date(2026, 8, 30)
DUE = date(2026, 9, 14)
NUMBER = "BL-2608-0141"

#: `US-CWP-033` §4, line for line. Amount is what the bill CHARGED; the tuple is
#: (kind, description, quantity, unit, unit_price, amount, service code).
WATER_LINES = (
    ("base", "Monthly service charge", None, None, None, "18.5000", "water"),
    ("usage", "Usage · first 2,000 gal", "2000", "gal", "0.0089", "17.8000", "water"),
    ("usage", "Usage · 2,001–5,000 gal", "2820", "gal", "0.0121", "34.1220", "water"),
)
SEWER_LINES = (("usage", "Share of water used", "4820", "gal", "0.0074", "35.6680", "sewer"),)
TRASH_LINES = (("usage", "Cart collection · 96 gal cart", "1", "cart", "22.0000", "22.0000", "trash"),)
#: Bill-level: a tax and a fee, neither of which names a service — PO ruling
#: 2026-08-11, *"Tax rates are for bill not for service"*.
BILL_LEVEL_LINES = (
    ("tax", "State utility tax", None, None, "0.042500", "5.4200", None),
    ("fee", "Regulatory fee", None, None, None, "8.6700", None),
)

SUBTOTAL = "128.0900"
TAX_TOTAL = "14.0900"
TOTAL = "142.1800"


def _service(tenant, code):
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Service.objects.filter(code=code).first()


def a_bill_with_lines(tenant, account, *, number=NUMBER, lines=None, payload=None):
    """One ISSUED bill and its lines, written as stage 6 writes them.

    ⚠ **THE BILL IS CREATED ISSUED RATHER THAN ISSUED AFTERWARDS**, and that is
    `DEF-155`'s lesson borrowed: an issued bill is immutable (hard rule 4), the
    triggers refuse an UPDATE, and a test that set a value after issue would
    ERROR rather than fail — which reads identically to a test nobody wrote.
    """
    rows = WATER_LINES + SEWER_LINES + TRASH_LINES + BILL_LEVEL_LINES if lines is None else lines
    invoice = billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=AUGUST,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        due_date=DUE,
        subtotal=Decimal(SUBTOTAL),
        tax_total=Decimal(TAX_TOTAL),
        total=Decimal(TOTAL),
        issued_at=datetime(2026, 8, 30, 9, 0, tzinfo=UTC),
        template_version=3,
        bill_payload=payload if payload is not None else {"services": []},
    )
    for kind, description, quantity, unit, unit_price, amount, service_code in rows:
        billing_models.InvoiceLine.objects.create(
            tenant=tenant,
            invoice=invoice,
            account=account,
            service=_service(tenant, service_code) if service_code else None,
            kind=kind,
            description=description,
            quantity=Decimal(quantity) if quantity is not None else None,
            unit=unit,
            unit_price=Decimal(unit_price) if unit_price is not None else None,
            amount=Decimal(amount),
            taxable=kind in ("usage", "base"),
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
        )
    return invoice


def an_isolation_account(tenant, actor, *, account_no="A-OAK-0001"):
    """A minimal account in the OTHER tenant, for the isolation case only.

    ⚠ **`seed_priced_addresses` IS PINE HILL'S OWN DATA AND REFUSES HERE.** It
    puts `1408 Elm St · A` on a named rate plan, and Oak Ridge has no such plan
    — `_put_on_plan` answers `NotFoundError`. The isolation case needs an
    account and a bill NUMBER, not a priced street, so it builds the account
    directly rather than bending a fixture that is about something else.

    ⚠ **AND ITS ADDRESS IS DELIBERATELY NOT ELM ST.** `seed_street` is
    idempotent on the ADDRESS LINE, and the suite runs on SQLite, which has no
    RLS (CLAUDE.md law 14's setting, in a second costume): seeding Elm St for a
    second tenant finds the FIRST tenant's premises and creates nothing, so the
    unit lookup answers `None` and the case dies in its own fixture rather than
    on the thing it is testing.
    """
    from apps.customers import models as customers_models
    from apps.metering import services as metering_services
    from apps.portal import sample_data as portal_sample

    with tenant_context(tenant.id):
        premises = metering_services.create_premises(
            actor,
            {
                "address_line": "77 Ridge Rd",
                "city": "Oak Ridge",
                "state": "TX",
                "postal_code": "78702",
                # `BR-MET-150` — a premises names a TYPED owner and the service
                # refuses to pick the category itself. The demo fixture answers
                # that for its own invented party, in one place, and this reuses
                # that answer rather than inventing a second one.
                "owner_id": portal_sample._fixture_owner(actor),
            },
        )
        unit = metering_services.create_unit(
            actor, {"premises_id": str(premises["id"]), "label": "Unit A"}
        )
        return customers_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            premises_id=premises["id"],
            status=customers_models.AccountStatus.objects.filter(tenant=tenant).first(),
            account_type=customers_models.AccountType.objects.first(),
            account_no=account_no,
        )


def read(tenant, account, *, number=NUMBER):
    with tenant_context(tenant.id):
        return billing_seam.bill_detail_for([account.pk], number=number, today=TODAY)


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · TC-2 — the lines, and the addition that is the point of the screen
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_033_tc1_the_lines_are_grouped_by_service_in_the_catalogue_order(
    pine_hill, sarah
):
    """`BR-CWP-044`. WATER · SEWER · TRASH · TAXES AND FEES, in `services.sort`.

    Alphabetical would put sewer before water here and after it on every other
    screen in the product, which is why the order is the catalogue's and is
    read off `charges_by_service` rather than sorted locally.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(pine_hill, account)
    bill = read(pine_hill, account)

    codes = [group["service"] for group in bill["groups"]]
    assert codes == ["water", "sewer", "trash", billing_seam.BILL_LEVEL_GROUP], codes
    water = bill["groups"][0]
    assert [line["amount_display"] for line in water["lines"]] == ["18.50", "17.80", "34.12"]
    assert bill["groups"][1]["lines"][0]["amount_display"] == "35.67"
    assert bill["groups"][2]["lines"][0]["amount_display"] == "22.00"
    assert [line["amount_display"] for line in bill["groups"][3]["lines"]] == ["5.42", "8.67"]


@pytest.mark.django_db
def test_us_cwp_033_tc2_THE_DISPLAYED_LINES_ADD_TO_THE_DISPLAYED_TOTAL(pine_hill, sarah):
    """⚠ **THE ARITHMETIC CHECK, AND IT IS THE STORY.**

    `18.50 + 17.80 + 34.12 + 35.67 + 22.00 = 128.09`, and
    `128.09 + 5.42 + 8.67 = 142.18` — **from the figures the screen prints**.

    ⚠ **THE FIXTURE IS DELIBERATELY NOT EXACT AT TWO DECIMALS.** Sewer stores
    `35.6680` and the regulatory fee `8.6700`; the water tier stores `34.1220`.
    A truncating display would print `35.66` and the column would foot to
    `128.08` against a stated `128.09` — a penny of disagreement, which is the
    support call this story exists to prevent. Rounding half-up is what makes
    the addition come out, and `core.money.finalize` is where that lives.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(pine_hill, account)
    bill = read(pine_hill, account)

    printed = [
        Decimal(line["amount_display"])
        for group in bill["groups"]
        for line in group["lines"]
    ]
    charges = [amount for amount in printed if amount not in (Decimal("5.42"), Decimal("8.67"))]
    assert sum(charges) == Decimal("128.09"), printed
    assert bill["subtotal_display"] == "128.09"
    assert bill["tax_display"] == "14.09"
    assert bill["total_display"] == "142.18"
    # ⚠ The identity a customer performs, on the printed strings, with no
    # tolerance: charges before tax + tax = total.
    assert Decimal(bill["subtotal_display"]) + Decimal(bill["tax_display"]) == Decimal(
        bill["total_display"]
    )


@pytest.mark.django_db
def test_us_cwp_033_tc3_a_tiered_usage_line_states_its_own_band_and_its_own_rate(
    pine_hill, sarah
):
    """`2,820 gal` in the `2,001–5,000` band, priced at its own rate.

    ⚠ **THE RATE SHOWS FOUR DECIMALS AND NOT TWO** — `OQ-620(a)`, PO 2026-08-27:
    *"A rate is not money and not a quantity - 4 decimal places"*. `0.0089`
    rounded to money's two would print `$0.01` and the line would not
    reconstruct.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(pine_hill, account)
    tiers = read(pine_hill, account)["groups"][0]["lines"]

    assert tiers[1]["quantity"] == "2000" and tiers[1]["unit"] == "gal"
    assert tiers[2]["quantity"] == "2820" and tiers[2]["unit"] == "gal"
    assert tiers[1]["rate"] == "0.0089", "a rate is 4dp, never money's 2"
    assert tiers[2]["rate"] == "0.0121"
    # `DEF-CWP-3967` — and the screen is told it is money PER A UNIT, so it can
    # draw `$0.0089 / gal` rather than a bare number.
    assert tiers[1]["rate_basis"] == "per_unit"
    assert tiers[1]["rate_percent"] is None


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CWP-3967` — the engine's own values, made readable
#
# ⚠ **NO GATE READS RENDERED OUTPUT (law 6) AND NO TEST COMPARED A BILL SCREEN
# WITH ITS SPEC**, so a bill showing correct figures in machine form passed
# everything. These assert the WIRE, which is what the screen can only draw
# what it is given.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_def_cwp_3967_a_rate_with_no_unit_is_a_PERCENTAGE_and_says_so(pine_hill, sarah):
    """`0.0625` on a tax line is `6.25%`, and the ×100 happens on the server.

    ⚠ **BOTH READINGS PRODUCE A WELL-FORMED STRING, WHICH IS WHY THIS IS A
    TEST.** `wording.percent_text` takes percentage POINTS: hand it the stored
    fraction and it prints `0.06%` for a six-per-cent tax; hand a points value
    to a fraction formatter and it prints `625.00%`. Nothing about either looks
    wrong on a screen.

    The discriminator is STRUCTURAL — a line priced off a meter carries a unit
    (hard rule 3), a line pricing a proportion does not — rather than a list of
    `kind` values somebody has to keep in step with every pricing model.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(
            pine_hill,
            account,
            lines=(
                ("usage", "water usage", "2000", "gal", "0.0089", "17.8000", "water"),
                ("tax", "Tax Texas State", None, None, "0.0625", "5.4200", None),
                ("base", "water base charge", None, None, None, "18.5000", "water"),
            ),
        )
    lines = {
        line["description"]: line
        for group in read(pine_hill, account)["groups"]
        for line in group["lines"]
    }

    metered = lines["water usage"]
    assert metered["rate_basis"] == "per_unit"
    assert metered["rate"] == "0.0089"
    assert metered["rate_percent"] is None

    tax = lines["Tax Texas State"]
    assert tax["rate_basis"] == "percent"
    # SIX POINT TWO FIVE, not 0.0625 and not 625.00 — hard rule 2's two padded
    # places on a percentage.
    assert tax["rate_percent"] == "6.25"

    # A line with no rate at all claims neither shape.
    base = lines["water base charge"]
    assert base["rate"] is None
    assert base["rate_basis"] is None
    assert base["rate_percent"] is None


@pytest.mark.django_db
def test_def_cwp_3967_a_percent_of_service_line_reads_as_a_percentage_too(
    pine_hill, sarah
):
    """`sewer usage — 40.00% of water usage charges` prices a PROPORTION.

    `percent_of_service` says so in its own words — *"No quantity and no unit:
    this line prices DOLLARS, not a metered volume"* — so the same structural
    test catches it without naming the model."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(
            pine_hill,
            account,
            lines=(
                ("usage", "sewer usage — 40.00% of water usage charges",
                 None, None, "0.4000", "35.6700", "sewer"),
            ),
        )
    line = read(pine_hill, account)["groups"][0]["lines"][0]
    assert line["rate_basis"] == "percent"
    assert line["rate_percent"] == "40.00", "two PADDED places — 40.00, never 40"


@pytest.mark.django_db
def test_us_cwp_033_tc4_NEGATIVE_no_quantity_is_ever_served_without_its_unit(
    pine_hill, sarah
):
    """⚠ **HARD RULE 3, ASSERTED ON EVERY ROW OF THE BILL.**

    `4,820` in a column headed *Quantity* is read as whatever unit the reader
    assumes. And the refusal is in the READ rather than on the screen: a line
    carrying a quantity and no unit serves `quantity: null`, so the wire cannot
    hand a screen a bare number to render even if a later lane forgets the rule.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(
            pine_hill,
            account,
            lines=WATER_LINES
            + (("usage", "Unmeasured usage", "999", None, None, "0.0000", "water"),),
        )
    bill = read(pine_hill, account)
    for group in bill["groups"]:
        for line in group["lines"]:
            assert (line["quantity"] is None) == (line["unit"] is None), line
            if line["quantity"] is not None:
                assert line["unit"], line
    naked = [
        line for line in bill["groups"][0]["lines"] if line["description"] == "Unmeasured usage"
    ]
    assert naked and naked[0]["quantity"] is None, "a unitless quantity is REFUSED, not printed"


@pytest.mark.django_db
def test_us_cwp_033_tc6_ELEVEN_SERVICES_GROUP_AND_FIRE_COUNTS(pine_hill, sarah):
    """`BR-RAT-024` — eleven services, and **fire is trash's arithmetic**.

    One 6" line at `$60.00` and two 2" lines at `$12.00` each reads
    **`$60.00 + 2 × $12.00`** on **TWO lines** in one group — `$84.00`. The
    size class picks the price and the COUNT multiplies it; nothing here sums
    the two rows into one, because the bill did not.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(
            pine_hill,
            account,
            lines=(
                ("usage", 'Fire line · 6"', "1", "line", "60.0000", "60.0000", "fire"),
                ("usage", 'Fire line · 2"', "2", "line", "12.0000", "24.0000", "fire"),
            ),
        )
    groups = read(pine_hill, account)["groups"]
    fire = [group for group in groups if group["service"] == "fire"]
    assert fire, [group["service"] for group in groups]
    assert len(fire[0]["lines"]) == 2, "fire COUNTS on two lines and is never collapsed"
    assert [line["amount_display"] for line in fire[0]["lines"]] == ["60.00", "24.00"]
    assert fire[0]["subtotal_display"] == "84.00"


@pytest.mark.django_db
def test_us_cwp_033_tc7_TENANT_ISOLATION_an_oak_ridge_session_is_refused(
    pine_hill, sarah, oak_ridge, elena
):
    """`BR-CWP-010` — both halves in the QUERY, proved with the SAME number.

    ⚠ **THE OAK RIDGE BILL CARRIES `BL-2608-0141` TOO.** A test using a
    different number would pass on the number being absent rather than on the
    account set being enforced, which is the check that matters.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    pine_account = elm_street_account(pine_hill, sarah)
    oak_account = an_isolation_account(oak_ridge, elena)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(pine_hill, pine_account)
    with tenant_context(oak_ridge.id):
        a_bill_with_lines(oak_ridge, oak_account)

    with tenant_context(oak_ridge.id):
        assert (
            billing_seam.bill_detail_for([oak_account.pk], number=NUMBER, today=TODAY) is not None
        )
        # The same number, asked for with Pine Hill's account set: nothing.
        assert (
            billing_seam.bill_detail_for([pine_account.pk], number=NUMBER, today=TODAY) is None
        )


@pytest.mark.django_db
def test_us_cwp_033_NEGATIVE_a_draft_bill_is_not_reachable_by_its_number(pine_hill, sarah):
    """`BR-CWP-041` — the portal sees nothing above the issued line.

    A draft carries a number from the moment it is created (`BR-BIL-063`), so
    guessing one is easy; the read refuses on STATUS and answers exactly what
    an unknown number answers.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        billing_models.Invoice.objects.create(
            tenant=pine_hill,
            account=account,
            invoice_no="BL-2609-0999",
            status=billing_models.INVOICE_DRAFT,
            service_date=AUGUST,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            total=Decimal("99.9900"),
        )
    assert read(pine_hill, account, number="BL-2609-0999") is None
    assert read(pine_hill, account, number="BL-9999-0000") is None


@pytest.mark.django_db
def test_us_cwp_033_B14_RULE_31_no_database_id_reaches_the_wire(pine_hill, sarah):
    """⚠ **NOT A STYLE CHECK — the staff row carries five ids and this drops
    every one.** `invoice_line_row` serves `id`, `gl_account_id`,
    `tariff_version_id`, `tax_id` and `charge_id`; a customer reads none of
    them. `accountDetailTabs.tsx` records that even EIGHT CHARACTERS of a uuid
    used as link text is the same breach as the whole of it, so the test is on
    the KEYS being absent rather than on their length.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(pine_hill, account)
    bill = read(pine_hill, account)

    forbidden = {"id", "gl_account_id", "tariff_version_id", "tax_id", "charge_id", "invoice_id"}
    assert not forbidden & set(bill), sorted(forbidden & set(bill))
    for group in bill["groups"]:
        for line in group["lines"]:
            assert not forbidden & set(line), sorted(forbidden & set(line))
    assert bill["number"] == NUMBER, "the reference is the number on the paper"


@pytest.mark.django_db
def test_us_cwp_033_tc9_the_rail_states_brought_forward_paid_since_and_owing(
    pine_hill, sarah
):
    """`$0.00` brought forward, `$0.00` paid since, `$142.18` owing.

    ⚠ **AN UNSTAMPED FIGURE IS `null` AND NEVER `0.00`.** `BR-BIL-035` writes
    NULLS rather than zeros when the payments seam was unreachable at issue, on
    purpose — *"0.00 would tell a customer in arrears that they are square"* —
    and this projection keeps that distinction rather than flattening it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(
            pine_hill,
            account,
            payload={
                "services": [],
                "previous_balance": "0.000000",
                "payments_credits": "0.000000",
                "total_due": TOTAL,
            },
        )
    rail = read(pine_hill, account)["account"]
    assert rail["this_bill"] == "142.18"
    assert rail["owing"] == "142.18"
    assert rail["brought_forward"] == "0.00"
    assert rail["paid_since"] == "0.00"


@pytest.mark.django_db
def test_us_cwp_033_a_bill_with_no_balance_stamp_states_the_absence_not_a_zero(
    pine_hill, sarah
):
    """The mirror of the case above, and the one that matters more."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        a_bill_with_lines(pine_hill, account)
    rail = read(pine_hill, account)["account"]
    assert rail["brought_forward"] is None, "an unstamped figure is ABSENT, never 0.00"
    assert rail["paid_since"] is None
