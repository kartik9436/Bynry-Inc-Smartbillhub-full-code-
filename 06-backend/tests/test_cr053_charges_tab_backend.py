# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 7 (serialize the tax authority and the charge code) and
#           task 9 (per-service subtotals — the one task in this CR with real
#           arithmetic; the CR marks it "Back — No", *"nothing computes these"*)
#           Screen: S30.3 Bill · Charges
# Rules:    B4.4 ❄️ FROZEN (round PER LINE ITEM, half-up, 2dp) · B4 CONFIRMED
#           2026-08-11 (a sum over lines is taken over the ROUNDED line amounts,
#           *"so the printed document foots against itself"*) · BR-BIL-069 (a
#           tax line names WHOSE tax it is) · BR-BIL-010 (a fee line names its
#           charge code) · BR-BIL-004 / hard rule 4 (issued history is
#           immutable — this whole surface is READ-only) · CLAUDE.md rule 2
#           (money stored 4dp / percent 6dp, DISPLAY 2dp, CHAR(3) currency,
#           never float) · PO ruling 2026-08-11 (*"Tax rates are for bill not
#           for service"*) · BR-TEN-025 (the seeded ten-service catalog order)
# ───────────────────────────────────────────────────────
"""The Charges tab's two backend halves, and what each may honestly say.

**TASK 9 IS THE ONE WITH ARITHMETIC, AND ITS WHOLE RISK IS ONE CHOICE.** A
subtotal is a sum over lines, and there are exactly two readings of that sum:

  * Σ finalize(line)  — add the amounts the bill PRINTS
  * finalize(Σ line)  — add the amounts the bill STORES, then round once

They differ by up to a cent per bucket, and B4 has already ruled between them
for the tax base, on 2026-08-11, in terms that are about sums-over-lines
generally and not about tax: *"a customer who adds up the four printed lines
and applies the rate gets $13.66 while the bill says $13.67, so the printed
document does not foot against itself"*. A per-service subtotal is read by a
customer doing exactly that addition, so it takes the same reading — Σ of the
rounded lines. `test_task9_rounding_follows_the_signed_reading` is that choice
made falsifiable: it is the only test here that would still pass if the rule
were read the other way round, so it asserts the FIGURE rather than the shape.

**WHAT THE GROUPING IS ALLOWED TO BE.** `invoice_lines.service_id` is written
by `stages/assemble_document._service_id_for` for `usage` and `base` lines and
for nothing else — a tax is a BILL-level charge (PO 2026-08-11) and a fee is a
fact about the ACCOUNT. So a per-service subtotal covers usage and base, every
other kind lands in a stated bill-level bucket, and NOTHING here reads a line's
description to decide which service it belongs to. Water and sewer are both
metered in kgal and both say "usage" — a text-derived grouping would put one
service's money under the other's heading and be right most of the time.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import selectors as billing_selectors
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# Fixtures — GT-10's bill, which is the reference bill for this whole file
#
#   usage (electric)  82.08   taxable
#   base  (electric)  18.50   taxable      -> electric subtotal 100.58
#   late fee           8.13   NOT taxable  ) bill-level, service_id NULL
#   tax  8.25% x 100.58 = 8.30             )                    16.43
#                                             invoices.total   117.01
#
# Every figure is B5-frozen (GT-10, re-signed 2026-08-10). Nothing in this file
# invents a money figure, so a failure here is this code's and never a fixture's.
# ══════════════════════════════════════════════════════════════════════════
def _service(code):
    return tenancy_models.Service.objects.get(code=code)


def a_line(tenant, invoice, account, **overrides):
    values = dict(
        tenant=tenant,
        invoice=invoice,
        account=account,
        kind="usage",
        description="Electric usage 684 kWh",
        quantity=Decimal("684"),
        unit="kWh",
        unit_price=Decimal("0.12"),
        amount=Decimal("82.08"),
        taxable=True,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
    )
    values.update(overrides)
    return billing_models.InvoiceLine.objects.create(**values)


def a_tax(tenant, *, authority="State of Texas", rate=Decimal("0.082500")):
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=authority, authority=authority, level="state"
    )
    return rating_models.Tax.objects.create(
        tenant=tenant,
        jurisdiction=jurisdiction,
        name="State sales tax",
        kind="percent",
        rate=rate,
    )


def a_charge(tenant, *, code="CR053-FEE", name="Late payment fee"):
    """A charge code of this tenant's own.

    ⚠ NOT `LATE`. The sample utility SEEDS a `LATE` row (`decisions.py`'s
    *"The seeded `LATE` row is `percent_with_minimum`"*) and `charges` is
    unique on `(tenant, code)`, so a fixture claiming that code fails with
    `UNIQUE constraint failed: charges.tenant_id, charges.code` — which is a
    fixture collision wearing the costume of a real defect.
    """
    return rating_models.Charge.objects.create(
        tenant=tenant, code=code, name=name, charge_type="penalty", amount_rule="flat"
    )


def gt10_bill(tenant, account, *, tax=None, charge=None):
    """GT-10's four lines on one invoice, with its frozen 117.01 total."""
    invoice = an_invoice(
        tenant,
        account,
        subtotal=Decimal("100.58"),
        tax_total=Decimal("8.30"),
        total=Decimal("117.01"),
    )
    electric = _service("electric")
    a_line(tenant, invoice, account, kind="usage", amount=Decimal("82.08"), service=electric)
    a_line(
        tenant,
        invoice,
        account,
        kind="base",
        description="Electric base charge",
        quantity=None,
        unit=None,
        unit_price=None,
        amount=Decimal("18.50"),
        service=electric,
    )
    a_line(
        tenant,
        invoice,
        account,
        kind="fee",
        description="Late payment fee",
        quantity=None,
        unit=None,
        unit_price=None,
        amount=Decimal("8.13"),
        taxable=False,
        service=None,
        charge=charge,
    )
    a_line(
        tenant,
        invoice,
        account,
        kind="tax",
        description="State sales tax 8.25%",
        quantity=None,
        unit=None,
        unit_price=None,
        amount=Decimal("8.30"),
        taxable=False,
        service=None,
        tax=tax,
    )
    return invoice


def detail_of(tenant, invoice_id):
    return api_call(
        billing_api.invoice_item,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        invoice_id=str(invoice_id),
    )


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 — the two stamps the payload never carried
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tax_line_names_its_authority(brazos, marcus):
    """BR-BIL-069: a tax line says WHOSE tax it is, in words.

    The $8.30 on GT-10 is one authority's; on the reference bill it is three
    (State of Texas 6.25% + Harris County 1.00% + City of Katy 1.00%), which is
    three debts and three returns to file. Until this key the payload carried
    `kind='tax'`, a wording and an amount, and the $6.29 could not be
    identified as Texas's.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        tax = a_tax(brazos, authority="State of Texas")
        invoice = gt10_bill(brazos, account, tax=tax)
        detail = billing_selectors.invoice_detail(invoice.pk)

    tax_lines = [line for line in detail["lines"] if line["kind"] == "tax"]
    assert len(tax_lines) == 1
    assert tax_lines[0]["tax_id"] == str(tax.pk)
    assert tax_lines[0]["tax_authority"] == "State of Texas"


def test_task7_authority_falls_back_to_the_jurisdiction_then_the_tax(brazos, marcus):
    """A half-filled jurisdiction row is still better than a uuid (DEF-206)."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="Harris County", authority=None
        )
        tax = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=jurisdiction, name="County sales tax", kind="percent"
        )
        invoice = gt10_bill(brazos, account, tax=tax)
        detail = billing_selectors.invoice_detail(invoice.pk)

    tax_line = next(line for line in detail["lines"] if line["kind"] == "tax")
    assert tax_line["tax_authority"] == "Harris County"


def test_task7_fee_line_names_its_charge_code(brazos, marcus):
    """BR-BIL-010 keys a fee's GL account on `charge_id`, and until this key the
    Charges tab could not say which code produced the line."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        charge = a_charge(brazos, code="CR053-LATE")
        invoice = gt10_bill(brazos, account, charge=charge)
        detail = billing_selectors.invoice_detail(invoice.pk)

    fee_line = next(line for line in detail["lines"] if line["kind"] == "fee")
    assert fee_line["charge_id"] == str(charge.pk)


def test_task7_absence_is_not_a_gap_on_a_usage_line(brazos, marcus):
    """A usage line names no tax and no charge code, and that is BY CONSTRUCTION
    (`assemble_document`: a tax is bill-level, a fee is an account fact). The
    keys are present and null rather than missing, so the screen renders an
    absence instead of a KeyError."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = gt10_bill(brazos, account, tax=a_tax(brazos), charge=a_charge(brazos))
        detail = billing_selectors.invoice_detail(invoice.pk)

    usage = next(line for line in detail["lines"] if line["kind"] == "usage")
    for key in ("tax_id", "tax_authority", "charge_id", "charge_code"):
        assert key in usage, f"{key} must be served under its contracted name"
        assert usage[key] is None


def test_task7_reaches_the_api_not_only_the_selector(brazos, marcus):
    """Hard-won law 2 — a serializer nothing serves is not a feature."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        tax = a_tax(brazos, authority="City of Katy")
        invoice = gt10_bill(brazos, account, tax=tax)
        response = detail_of(brazos, invoice.pk)

    assert response.status_code == 200
    tax_line = next(line for line in response.data["lines"] if line["kind"] == "tax")
    assert tax_line["tax_authority"] == "City of Katy"


# ══════════════════════════════════════════════════════════════════════════
# TASK 9 — per-service subtotals
# ══════════════════════════════════════════════════════════════════════════
def test_task9_gt10_electric_subtotal_and_tie_out(brazos, marcus):
    """The worked figure, entirely in B5-frozen numbers.

    electric  82.08 + 18.50 = **100.58**
    bill-level 8.13 +  8.30 =   16.43
                              -------
                               117.01 = invoices.total (GT-10, frozen)
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = gt10_bill(brazos, account, tax=a_tax(brazos), charge=a_charge(brazos))
        detail = billing_selectors.invoice_detail(invoice.pk)

    block = detail["charges_by_service"]
    assert [row["service"] for row in block["services"]] == ["electric"]
    electric = block["services"][0]
    assert electric["subtotal_display"] == "100.58"
    assert electric["line_count"] == 2

    assert block["bill_level"]["subtotal_display"] == "16.43"
    assert sorted(block["bill_level"]["kinds"]) == ["fee", "tax"]

    tie = block["tie_out"]
    assert tie["ties_out"] is True
    assert tie["invoice_total"] == "117.010000"
    assert tie["delta"] == "0.000000"


def test_task9_rounding_follows_the_signed_reading(brazos, marcus):
    """⚠ THE ONE TEST THAT PINS THE CHOICE B4 ALREADY MADE.

    Three electric lines of 33.333333 each.

      Σ finalize(line) = 33.33 + 33.33 + 33.33 = **99.99**   <- what B4 rules
      finalize(Σ line) = finalize(99.999999)   =   100.00    <- one cent adrift

    A customer adding the three printed lines gets 99.99. If this assertion is
    ever changed to 100.00, the bill has stopped footing against itself and
    that is a signed-figure change needing a finance re-sign (HUMAN-GUIDE §6),
    never an edit here.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = an_invoice(
            brazos,
            account,
            subtotal=Decimal("99.99"),
            tax_total=Decimal("0"),
            total=Decimal("99.99"),
        )
        electric = _service("electric")
        for _ in range(3):
            a_line(brazos, invoice, account, amount=Decimal("33.333333"), service=electric)
        detail = billing_selectors.invoice_detail(invoice.pk)

    row = detail["charges_by_service"]["services"][0]
    assert row["subtotal_display"] == "99.99"
    assert row["subtotal"] == "99.990000"


def test_task9_services_take_the_seeded_catalog_order(brazos, marcus):
    """BR-RAT-024's ten services have a seed order and it is not alphabetical.
    Water before sewer, because `services.sort` says so — a bill that lists its
    services differently from every other screen makes a clerk re-read it."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = an_invoice(
            brazos, account, subtotal=Decimal("30"), tax_total=Decimal("0"), total=Decimal("30")
        )
        for code in ("sewer", "water", "electric"):
            a_line(
                brazos,
                invoice,
                account,
                amount=Decimal("10.00"),
                service=_service(code),
                description=f"{code} usage",
            )
        detail = billing_selectors.invoice_detail(invoice.pk)

    codes = [row["service"] for row in detail["charges_by_service"]["services"]]
    seeded = list(
        tenancy_models.Service.objects.filter(code__in=codes)
        .order_by("sort", "code")
        .values_list("code", flat=True)
    )
    assert codes == seeded
    assert codes != sorted(codes), "an alphabetical order would pass by accident here"


def test_task9_a_drift_is_reported_and_never_reconciled(brazos, marcus):
    """BR-BIL-032's posture, applied to this block: drift can never be silent.

    The rows say 100.58 and the invoice says 117.01 because the fee and the tax
    rows were never written. This block STATES the gap; it must not adjust
    either figure to make them agree, and it must not raise — a detail endpoint
    that 500s hides the one bill somebody needs to look at.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = an_invoice(
            brazos,
            account,
            subtotal=Decimal("100.58"),
            tax_total=Decimal("8.30"),
            total=Decimal("117.01"),
        )
        electric = _service("electric")
        a_line(brazos, invoice, account, amount=Decimal("82.08"), service=electric)
        a_line(
            brazos,
            invoice,
            account,
            kind="base",
            amount=Decimal("18.50"),
            service=electric,
            quantity=None,
            unit=None,
        )
        detail = billing_selectors.invoice_detail(invoice.pk)

    tie = detail["charges_by_service"]["tie_out"]
    assert tie["ties_out"] is False
    assert tie["lines_total"] == "100.580000"
    assert tie["invoice_total"] == "117.010000"
    assert tie["delta"] == "-16.430000"


def test_task9_money_travels_with_its_currency_and_never_as_a_number(brazos, marcus):
    """CLAUDE.md rule 2 — CHAR(3) partner, never a float on the wire."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = gt10_bill(brazos, account)
        detail = billing_selectors.invoice_detail(invoice.pk)

    block = detail["charges_by_service"]
    assert block["currency"] == "USD"
    for value in (
        block["services"][0]["subtotal"],
        block["services"][0]["subtotal_display"],
        block["bill_level"]["subtotal"],
        block["tie_out"]["lines_total"],
        block["tie_out"]["delta"],
    ):
        assert isinstance(value, str), f"{value!r} must be a string, never a float"


def test_task9_a_bill_with_no_service_bearing_line_states_an_empty_list(brazos, marcus):
    """A fee-only bill (BR-BIL-012's connection charge, a one-time bill) has no
    per-service anything. An EMPTY list is the honest answer; a zero-valued
    'electric' row would claim the bill charged for electricity."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = an_invoice(
            brazos, account, subtotal=Decimal("45"), tax_total=Decimal("0"), total=Decimal("45")
        )
        a_line(
            brazos,
            invoice,
            account,
            kind="fee",
            description="Reconnect fee",
            quantity=None,
            unit=None,
            unit_price=None,
            amount=Decimal("45.00"),
            taxable=False,
            service=None,
        )
        detail = billing_selectors.invoice_detail(invoice.pk)

    block = detail["charges_by_service"]
    assert block["services"] == []
    assert block["bill_level"]["subtotal_display"] == "45.00"
    assert block["tie_out"]["ties_out"] is True


def test_task9_is_read_only(brazos, marcus):
    """Hard rule 4. The block is derived on every read and stores nothing —
    proved by asserting no row's `updated_at` moves across two reads."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        invoice = gt10_bill(brazos, account)
        before = list(
            billing_models.InvoiceLine.objects.filter(invoice=invoice)
            .order_by("id")
            .values_list("id", "updated_at", "amount")
        )
        first = billing_selectors.invoice_detail(invoice.pk)
        second = billing_selectors.invoice_detail(invoice.pk)
        after = list(
            billing_models.InvoiceLine.objects.filter(invoice=invoice)
            .order_by("id")
            .values_list("id", "updated_at", "amount")
        )
        invoice.refresh_from_db()

    assert before == after
    assert invoice.total == Decimal("117.010000")
    # The block is DERIVED, so two reads of an unchanged bill agree exactly. A
    # figure that moved between them would mean the subtotal had been stored
    # somewhere and re-read, which is a second source of truth for money.
    assert first["charges_by_service"] == second["charges_by_service"]
