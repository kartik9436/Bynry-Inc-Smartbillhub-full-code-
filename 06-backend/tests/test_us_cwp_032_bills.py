# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-032 (EP-CWP-07) — bills: owing is a separate column from
#           amount, and a corrected bill names its replacement. Screen: CWP-027
# Rules:    BR-CWP-043 (owing and amount are TWO columns; part-paid is a THIRD
#           state) · BR-CWP-042 (the corrected pair are both present, the
#           original naming its replacement) · BR-CWP-041 (nothing above the
#           issued bill) · B14 rule 31 (no database id is a visible value) ·
#           CLAUDE.md hard rule 2
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `bills_for` · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-032`'s cases — and the two the wireframe is really about.

⚠ **THE WHOLE SCREEN EXISTS FOR TWO DISTINCTIONS.** A bill that CHARGED
`$142.18` and still OWES `$102.18` is neither paid nor unpaid, and a list that
had to choose would be wrong either way — showing it PAID asks nobody for the
`$102.18`, showing it DUE asks for `$142.18` twice. And a bill that was
CORRECTED stays in the list naming its replacement, because a customer holding
a bank statement has to be able to reconcile it against something.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.portal.seams import billing_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)
from tests.test_us_cwp_024_balance import allocate

TODAY = date(2026, 9, 2)
AUGUST = date(2026, 8, 26)
DUE_SOON = date(2026, 9, 14)
DUE_PAST = date(2026, 7, 14)

#: The demo script's own figures.
CURRENT = "142.1800"
PART_PAID_AGAINST = "40.0000"
PART_PAID_OWING = Decimal("102.1800")
ORIGINAL = "154.9000"
REPLACEMENT = "129.0200"


def read(tenant, account):
    with tenant_context(tenant.id):
        return billing_seam.bills_for([account.pk], today=TODAY)


@pytest.mark.django_db
def test_us_cwp_032_tc1_a_bill_shows_what_it_CHARGED_and_what_it_still_OWES(
    pine_hill, sarah
):
    """`BR-CWP-043` — two columns, and the screen never subtracts."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
    rows = read(pine_hill, account)
    assert len(rows) == 1
    assert rows[0]["total"] == CURRENT
    assert rows[0]["owing"] == CURRENT
    assert rows[0]["state"] == billing_seam.BILL_DUE


@pytest.mark.django_db
def test_us_cwp_032_tc3_a_part_paid_bill_is_a_THIRD_state_and_not_a_shade(
    pine_hill, sarah
):
    """⚠ **NEITHER PAID NOR DUE.** `$142.18` charged with `$40.00` against it
    owes `$102.18`, and the state says so in its own word — because a list that
    had to pick one of the other two would ask for the wrong money."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
        allocate(pine_hill, account, bill, PART_PAID_AGAINST)
    row = read(pine_hill, account)[0]
    assert row["total"] == CURRENT, "what it charged never moves"
    assert Decimal(row["owing"]) == PART_PAID_OWING
    assert row["state"] == billing_seam.BILL_PART_PAID
    assert row["state"] not in (billing_seam.BILL_PAID, billing_seam.BILL_DUE)


@pytest.mark.django_db
def test_us_cwp_032_a_settled_bill_reads_PAID_and_keeps_its_amount(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0139", total="138.4400",
            issued_on=date(2026, 7, 26), due_on=date(2026, 8, 14),
        )
        allocate(pine_hill, account, bill, "138.4400")
    row = read(pine_hill, account)[0]
    assert row["state"] == billing_seam.BILL_PAID
    assert row["owing"] == "0.0000"
    assert row["total"] == "138.4400", "a paid bill still says what it charged"


@pytest.mark.django_db
def test_us_cwp_032_an_unpaid_bill_past_its_date_reads_OVERDUE(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2606-0111", total="412.6000",
            issued_on=date(2026, 6, 26), due_on=DUE_PAST,
        )
    assert read(pine_hill, account)[0]["state"] == billing_seam.BILL_OVERDUE


@pytest.mark.django_db
def test_us_cwp_032_tc4_the_corrected_pair_are_BOTH_present_and_name_each_other(
    pine_hill, sarah
):
    """`BR-CWP-042`. ⚠ **DROPPING THE ORIGINAL WOULD LEAVE A CUSTOMER WITH A
    BANK STATEMENT THEY CANNOT RECONCILE.** `$154.90` was charged, `$129.02`
    replaced it, and both rows are in the list — the first naming the second."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        original = an_issued_bill(
            pine_hill, account, number="BL-2606-0137", total=ORIGINAL,
            issued_on=date(2026, 6, 26), due_on=date(2026, 7, 14),
        )
        replacement = an_issued_bill(
            pine_hill, account, number="BL-2606-0147", total=REPLACEMENT,
            issued_on=date(2026, 6, 28), due_on=date(2026, 7, 14),
        )
        replacement.corrects_invoice = original
        replacement.save(update_fields=["corrects_invoice"])
        original.status = billing_models.INVOICE_CORRECTED
        original.save(update_fields=["status"])

    rows = {row["number"]: row for row in read(pine_hill, account)}
    assert set(rows) == {"BL-2606-0137", "BL-2606-0147"}, rows
    assert rows["BL-2606-0137"]["state"] == billing_seam.BILL_CORRECTED
    assert rows["BL-2606-0137"]["replaced_by"] == "BL-2606-0147"
    assert rows["BL-2606-0147"]["replaces"] == "BL-2606-0137"
    # ⚠ B14 rule 31 — the pair name each other by the number on the paper.
    assert str(original.pk) not in str(rows)


@pytest.mark.django_db
def test_us_cwp_032_tc2_a_draft_bill_is_not_in_the_list(pine_hill, sarah):
    """`BR-CWP-041` — a draft is the utility's working copy, and a customer who
    saw one would ring up about a figure that is going to change."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
        billing_models.Invoice.objects.create(
            tenant=pine_hill, account=account, invoice_no="BL-2609-DRAFT",
            status=billing_models.INVOICE_DRAFT, service_date=date(2026, 9, 1),
            period_start=date(2026, 8, 27), period_end=date(2026, 9, 26),
            due_date=date(2026, 10, 14), subtotal=Decimal("999.99"),
            tax_total=Decimal("0"), total=Decimal("999.99"),
        )
    numbers = [row["number"] for row in read(pine_hill, account)]
    assert numbers == ["BL-2608-0141"]


@pytest.mark.django_db
def test_us_cwp_032_the_body_carries_no_database_id(pine_hill, sarah):
    """B14 rule 31 — the visible reference is the number on the paper."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
    row = read(pine_hill, account)[0]
    assert set(row) == {
        "number", "issued_on", "due_on", "total", "currency",
        "period_start", "period_end", "owing", "state", "replaced_by", "replaces",
        #: `DEF-CWP-3980` — the two the drawn columns needed. Neither is an id;
        #: this assertion is the reason to be sure of that, and it is why the
        #: key set is pinned WHOLE rather than checked for the absence of `id`.
        "due_in_days", "usage",
    }, row


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CWP-3980` — the columns `CWP-027` draws that this read could not answer
#
# ⚠ **THE PAYLOAD WAS ALREADY RIGHT ABOUT THE PERIOD AND THE SCREEN IGNORED
# IT.** `period_start` and `period_end` have been served on every row since
# this read was written. What was genuinely missing was the USAGE and the
# COUNTDOWN, and both are added here rather than in the browser for the same
# reason the owing figure is: a second answer computed one layer up is free to
# disagree with the first.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_def_cwp_3980_the_row_says_what_the_bill_charged_for_with_its_unit(
    pine_hill, sarah
):
    """CLAUDE.md hard rule 3 — a quantity always carries its unit."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
        # Two units on one bill, and a BASE line that is not a usage at all.
        for unit, quantity in (("gal", "4820"), ("therm", "31")):
            billing_models.InvoiceLine.objects.create(
                tenant=pine_hill, account=account, invoice=bill, kind="usage",
                description=f"usage {unit}", quantity=Decimal(quantity), unit=unit,
                amount=Decimal("10.0000"),
            )
        billing_models.InvoiceLine.objects.create(
            tenant=pine_hill, account=account, invoice=bill, kind="base",
            description="base charge", amount=Decimal("15.0000"),
        )
    row = read(pine_hill, account)[0]
    # ⚠ **TWO FIGURES AND NO THIRD ONE.** Adding 4,820 gal to 31 therm would
    # invent a number in a unit that does not exist.
    # Ordered by UNIT so a bill reads the same way every time it is opened.
    assert row["usage"] == [
        {"quantity_display": "4820", "unit": "gal"},
        {"quantity_display": "31", "unit": "therm"},
    ], row["usage"]
    assert all(one["unit"] for one in row["usage"]), "a bare quantity must never be served"


@pytest.mark.django_db
def test_def_cwp_3980_a_base_only_bill_has_no_usage_rather_than_a_zero(pine_hill, sarah):
    """`BR-CWP-093` — a trash-only bill charged for nothing MEASURED, and `0`
    in a usage column would say the meter read nothing."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0142", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
        billing_models.InvoiceLine.objects.create(
            tenant=pine_hill, account=account, invoice=bill, kind="base",
            description="trash base charge", amount=Decimal("15.0000"),
        )
    assert read(pine_hill, account)[0]["usage"] == []


@pytest.mark.django_db
def test_def_cwp_3980_the_countdown_is_the_servers_and_agrees_with_the_state(
    pine_hill, sarah
):
    """The chip reads *Due in 12 days*, and the count comes from the same
    `today` the state word did.

    ⚠ **THAT AGREEMENT IS THE WHOLE REASON IT IS COMPUTED HERE.** A browser
    subtracting its own clock from a due date would draw *Due in 1 day* inside
    a chip this function had already called `overdue`, for every customer whose
    device sits a time zone east of the utility."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_SOON,
        )
        an_issued_bill(
            pine_hill, account, number="BL-2607-0111", total=CURRENT,
            issued_on=AUGUST, due_on=DUE_PAST,
        )
    rows = {row["number"]: row for row in read(pine_hill, account)}
    # 2026-09-14 minus 2026-09-02 — the figure the drawing prints.
    assert rows["BL-2608-0141"]["due_in_days"] == 12
    assert rows["BL-2608-0141"]["state"] == "due"
    # Past due counts the other way, and the SIGN is what keeps the two
    # agreeing: a positive count beside `overdue` would be a contradiction.
    assert rows["BL-2607-0111"]["due_in_days"] == -50
    assert rows["BL-2607-0111"]["state"] == "overdue"


@pytest.mark.django_db
def test_def_cwp_3980_a_bill_with_no_due_date_has_no_countdown(pine_hill, sarah):
    """`None` is a real answer. A countdown invented from a date that is not
    there would be a figure with nothing behind it."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2608-0141", total=CURRENT, issued_on=AUGUST,
        )
        billing_models.Invoice.objects.filter(pk=bill.pk).update(due_date=None)
    assert read(pine_hill, account)[0]["due_in_days"] is None


@pytest.mark.django_db
def test_us_cwp_032_a_new_customer_gets_an_EMPTY_list_and_not_a_blank_table(
    pine_hill, sarah
):
    """`BR-CWP-093` — the screen says what will fill it. An empty LIST is what
    lets it; a row of dashes would not."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    assert read(pine_hill, account) == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-032@this-commit (EP-CWP-07 story + BR-CWP-041/042/043 verbatim)
# generated: 2026-09-04 by the CR-068 wave G build lane
# checklist: A✔ B✔ C✔ D✔(api.py bills) E=the screen's F✔ G✔ H=n/a(owing comes from payments, never recomputed)
# gates: pytest tests/test_us_cwp_032_bills.py · G81
# exceptions: the corrected pair is written through the ORM — this story is a READ over bills that corrections.py already produces
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
