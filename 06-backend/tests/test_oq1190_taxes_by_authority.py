# ── Trace ──────────────────────────────────────────────
# Question: OQ-1190 — CLOSED 2026-08-31. PO verbatim: *"(a) Add a per-authority
#           subtotal to the bill and the finance screens"*. Its worked case: a
#           bill charges two authorities and the only figure the product
#           published was the two added together, while a return is filed PER
#           AUTHORITY.
#           Screens: S30.3 Bill · Charges · S41 Taxes & Remittance
# Rules:    B4.4 ❄️ FROZEN (round PER LINE ITEM, half-up, 2dp) · B4 CONFIRMED
#           2026-08-11 (a sum over lines is taken over the ROUNDED line
#           amounts, *"so the printed document foots against itself"*) ·
#           BR-BIL-069 (a tax line names WHOSE tax it is) · BR-BIL-010 (the GL
#           stamp) · PO 2026-08-11 (*"Tax rates are for bill not for service"*,
#           UNTOUCHED by this) · CLAUDE.md rule 2 (4dp stored, 2dp displayed,
#           CHAR(3), never float) · hard rule 4 (read-only over issued history)
# Defects:  DEF-466 (a non-vacuous assertion asks BOTH that the wanted set is
#           non-empty AND that the unwanted set is empty) — every figure here is
#           asserted GREATER THAN ZERO as well as correct, so a block that
#           answered `[]` or all-zeros fails rather than passing quietly
# ───────────────────────────────────────────────────────
"""What each tax authority is owed on one bill, and why the sum is the one B4 chose.

**THE WHOLE RISK IS ONE ARITHMETIC CHOICE, AND IT WAS ALREADY MADE.** A subtotal
is a sum over lines and there are exactly two readings:

    Σ finalize(line)   add the amounts the bill PRINTS      <- THIS ONE
    finalize(Σ line)   add what it STORES, then round once

B4 ruled between them on 2026-08-11, for the tax base, in terms about
sums-over-lines generally: *"a customer who adds up the four printed lines and
applies the rate gets $13.66 while the bill says $13.67, so the printed document
does not foot against itself"* — the ROUNDED addends, chosen for
**reproducibility, not precision**.

`test_the_rounding_follows_the_signed_reading` is that choice made falsifiable.
It is the only case here that would still pass with the rule read the other way
round, so it asserts the FIGURE — the repo's own worked pair, three lines of
`33.333333` subtotalling to **99.99** and not `100.00`.

**WHAT THIS DOES NOT DO, and a test says so out loud.** It does not move tax onto
services. The 2026-08-11 ruling stands: `charges_by_service` still puts every tax
line in its one `bill_level` bucket, and this is a SECOND grouping of the same
immutable rows beside it, on the axis a remittance return is filed on. Two
groupings of one set of lines cannot disagree; a re-attribution would.
"""

from datetime import date
from decimal import Decimal

import pytest

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
# Fixtures — THE TWO-AUTHORITY BILL OQ-1190 IS ABOUT
#
#   usage (water)  223.60   taxable
#   base  (water)   15.00   taxable        -> water subtotal        238.60
#   tax   Bexar County Tax Office            4.77  )  tax_total      19.68
#   tax   Texas Comptroller of Public Accts 14.91  )
#                                              invoices.total       258.28
#
# These are the SEEDED reference bill `BL-2608-000094`'s own figures, read out
# of a real database rather than invented here, so a failure is this code's.
# ══════════════════════════════════════════════════════════════════════════
BEXAR = "Bexar County Tax Office"
TEXAS = "Texas Comptroller of Public Accounts"


def _service(code):
    return tenancy_models.Service.objects.get(code=code)


def a_tax(tenant, *, authority, name, rate, level="county"):
    """A tax whose JURISDICTION names the authority.

    `tax_authority_label_for_tax` resolves three sources most specific first —
    the jurisdiction's `authority`, then its `name`, then the tax's own name —
    so the fixture sets `authority` and the label is the authority, which is
    what a clerk files a return with.
    """
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=authority, authority=authority, level=level
    )
    return rating_models.Tax.objects.create(
        tenant=tenant, jurisdiction=jurisdiction, name=name, kind="percent", rate=rate
    )


def a_line(tenant, invoice, account, **overrides):
    values = dict(
        tenant=tenant,
        invoice=invoice,
        account=account,
        kind="usage",
        description="water usage",
        quantity=Decimal("43"),
        unit="kgal",
        unit_price=Decimal("5.20"),
        amount=Decimal("223.60"),
        taxable=True,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    values.update(overrides)
    return billing_models.InvoiceLine.objects.create(**values)


def two_authority_bill(tenant, account, *, local=None, state=None):
    """`BL-2608-000094`'s four lines, with its `19.68` tax total."""
    invoice = an_invoice(
        tenant,
        account,
        subtotal=Decimal("238.60"),
        tax_total=Decimal("19.68"),
        total=Decimal("258.28"),
    )
    water = _service("water")
    a_line(tenant, invoice, account, kind="usage", amount=Decimal("223.60"), service=water)
    a_line(
        tenant,
        invoice,
        account,
        kind="base",
        description="water base charge",
        quantity=None,
        unit=None,
        unit_price=None,
        amount=Decimal("15.00"),
        service=water,
    )
    a_line(
        tenant,
        invoice,
        account,
        kind="tax",
        description="Tax Local",
        quantity=None,
        unit=None,
        unit_price=Decimal("0.02"),
        amount=Decimal("4.77"),
        taxable=False,
        service=None,
        tax=local,
    )
    a_line(
        tenant,
        invoice,
        account,
        kind="tax",
        description="Tax Texas State",
        quantity=None,
        unit=None,
        unit_price=Decimal("0.0625"),
        amount=Decimal("14.91"),
        taxable=False,
        service=None,
        tax=state,
    )
    return invoice


@pytest.fixture
def bill(brazos, marcus):
    """The two-authority bill, its account and its two taxes, inside the tenant."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        local = a_tax(
            brazos, authority=BEXAR, name="Local · Bexar County", rate=Decimal("0.020000")
        )
        state = a_tax(
            brazos,
            authority=TEXAS,
            name="TX State Utility Tax",
            rate=Decimal("0.062500"),
            level="state",
        )
        invoice = two_authority_bill(brazos, account, local=local, state=state)
        yield {"invoice": invoice, "account": account, "local": local, "state": state}


def block_of(invoice):
    return billing_selectors.invoice_detail(invoice.id)["taxes_by_authority"]


# ══════════════════════════════════════════════════════════════════════════
# THE RULING
# ══════════════════════════════════════════════════════════════════════════
def test_each_authority_gets_its_own_subtotal_and_they_foot_to_the_bill(brazos, marcus, bill):
    """The PO's ruling, worked: 4.77 + 14.91 = 19.68, and 19.68 is the bill's own."""
    with tenant_ctx(brazos):
        block = block_of(bill["invoice"])

    rows = {row["authority"]: row for row in block["authorities"]}
    # NON-VACUOUS (DEF-466): the wanted set is non-empty AND every figure is
    # above zero, so an empty block or an all-zero one FAILS rather than
    # satisfying a shape assertion.
    assert set(rows) == {BEXAR, TEXAS}
    for authority, row in rows.items():
        assert Decimal(row["subtotal_display"]) > Decimal("0"), (
            f"{authority} subtotal is not greater than zero — a per-authority figure of "
            f"0.00 on a screen a return is filed from reads as 'this authority is owed "
            f"nothing'"
        )
        assert row["line_count"] >= 1

    assert rows[BEXAR]["subtotal_display"] == "4.77"
    assert rows[TEXAS]["subtotal_display"] == "14.91"
    # THE FOOTING, which is the whole point of the question.
    assert block["tie_out"]["ties_out"] is True
    assert block["tie_out"]["authorities_total_display"] == "19.68"
    assert block["tie_out"]["tax_total_display"] == "19.68"
    assert Decimal(block["tie_out"]["delta"]) == Decimal("0")
    assert (
        Decimal(rows[BEXAR]["subtotal_display"]) + Decimal(rows[TEXAS]["subtotal_display"])
        == Decimal(block["tie_out"]["tax_total_display"])
    )


def test_the_rounding_follows_the_signed_reading(brazos, marcus):
    """Σ finalize(line), never finalize(Σ line) — B4's 2026-08-11 ruling.

    ⚠ **THE ONLY CASE HERE THAT WOULD STILL PASS WITH THE RULE READ THE OTHER
    WAY ROUND**, which is why it asserts the FIGURE and not the shape. Three
    lines of `33.333333` under one authority:

        Σ finalize  =  33.33 + 33.33 + 33.33  =  **99.99**
        finalize Σ  =  finalize(99.999999)    =    100.00

    `99.99` is what the printed lines add to. The other reading puts a cent on
    the bill that appears in no line.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-33333", label="Unit H")
        authority = a_tax(
            brazos, authority="Harris County", name="Harris local", rate=Decimal("0.010000")
        )
        invoice = an_invoice(
            brazos,
            account,
            subtotal=Decimal("0"),
            invoice_no="BL-2608-000333",
            tax_total=Decimal("99.99"),
            total=Decimal("99.99"),
        )
        for _ in range(3):
            a_line(
                brazos,
                invoice,
                account,
                kind="tax",
                description="Harris local tax",
                quantity=None,
                unit=None,
                unit_price=None,
                amount=Decimal("33.333333"),
                taxable=False,
                service=None,
                tax=authority,
            )
        block = block_of(invoice)

    row = block["authorities"][0]
    assert row["line_count"] == 3
    assert row["subtotal_display"] == "99.99", (
        "the subtotal added the STORED amounts and rounded once (100.00). B4's ruling of "
        "2026-08-11 takes the sum over the ROUNDED line amounts, so the printed document "
        "foots against itself."
    )
    assert Decimal(row["subtotal_display"]) > Decimal("0")


def test_the_authority_account_comes_from_the_stamp_not_a_lookup(brazos, marcus, bill):
    """`OQ-1190` sub-question (b) — answered from `invoice_lines.gl_account_id`.

    BR-BIL-010: the account is STAMPED at issue and read back, never
    re-resolved. It is what joins the bill's per-authority figure to the books
    on S41.
    """
    with tenant_ctx(brazos):
        stamped = "01a055fa-a958-7f06-9af8-c1047677e9b6"
        billing_models.InvoiceLine.objects.filter(
            invoice=bill["invoice"], tax=bill["local"]
        ).update(gl_account_id=stamped)
        block = block_of(bill["invoice"])

    bexar = next(row for row in block["authorities"] if row["authority"] == BEXAR)
    assert bexar["liability_account_id"] == stamped
    assert bexar["liability_account_conflict"] is False


def test_two_accounts_under_one_authority_is_stated_not_picked(brazos, marcus):
    """A posting fault must not be buried by naming one of the two accounts."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-22222", label="Unit S")
        authority = a_tax(
            brazos, authority="Split County", name="Split local", rate=Decimal("0.01")
        )
        invoice = an_invoice(
            brazos,
            account,
            subtotal=Decimal("0"),
            invoice_no="BL-2608-000222",
            tax_total=Decimal("2.00"),
            total=Decimal("2.00"),
        )
        for gl in (
            "01a055fa-a958-7f06-9af8-c1047677e9b6",
            "01a055fa-a96b-77f9-9db0-00daa78ea261",
        ):
            a_line(
                brazos,
                invoice,
                account,
                kind="tax",
                description="Split local tax",
                quantity=None,
                unit=None,
                unit_price=None,
                amount=Decimal("1.00"),
                taxable=False,
                service=None,
                tax=authority,
                gl_account_id=gl,
            )
        block = block_of(invoice)

    row = block["authorities"][0]
    assert row["liability_account_id"] is None
    assert row["liability_account_conflict"] is True
    # The MONEY is still right — only the account is withheld.
    assert row["subtotal_display"] == "2.00"


def test_an_unstamped_tax_line_reaches_the_tie_out_and_no_authority(brazos, marcus):
    """A bill issued before BR-BIL-069's column: its money counts, its debt is nobody's."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-44444", label="Unit U")
        invoice = an_invoice(
            brazos,
            account,
            invoice_no="BL-2608-000444",
            subtotal=Decimal("0"),
            tax_total=Decimal("3.25"),
            total=Decimal("3.25"),
        )
        a_line(
            brazos,
            invoice,
            account,
            kind="tax",
            description="Tax",
            quantity=None,
            unit=None,
            unit_price=None,
            amount=Decimal("3.25"),
            taxable=False,
            service=None,
            tax=None,
        )
        block = block_of(invoice)

    assert block["authorities"] == []
    assert block["unstamped"]["line_count"] == 1
    assert block["unstamped"]["subtotal_display"] == "3.25"
    # It reaches the tie-out — money on the bill is never dropped out of the sum.
    assert block["tie_out"]["ties_out"] is True
    assert block["tie_out"]["authorities_total_display"] == "3.25"


def test_a_bill_with_no_tax_answers_an_empty_list_not_a_zero_row(brazos, marcus):
    """A zero row would claim a debt to an authority this bill never charged."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-55555", label="Unit N")
        invoice = an_invoice(
            brazos,
            account,
            invoice_no="BL-2608-000555",
            subtotal=Decimal("10.00"),
            tax_total=Decimal("0"),
            total=Decimal("10.00"),
        )
        a_line(brazos, invoice, account, amount=Decimal("10.00"), service=_service("water"))
        block = block_of(invoice)

    assert block["authorities"] == []
    assert block["unstamped"]["line_count"] == 0
    assert block["tie_out"]["ties_out"] is True


def test_a_disagreement_is_stated_and_never_corrected(brazos, marcus):
    """`BR-BIL-032`'s evidence survives — the read reports, it does not balance."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-99999", label="Unit D")
        authority = a_tax(
            brazos, authority="Drifted County", name="Drift local", rate=Decimal("0.01")
        )
        invoice = an_invoice(
            brazos,
            account,
            subtotal=Decimal("0"),
            # The bill CLAIMS 9.00 and its one line is 5.00 — a drifted bill,
            # which is exactly the bill somebody needs to look at.
            invoice_no="BL-2608-000999",
            tax_total=Decimal("9.00"),
            total=Decimal("9.00"),
        )
        a_line(
            brazos,
            invoice,
            account,
            kind="tax",
            description="Drift local tax",
            quantity=None,
            unit=None,
            unit_price=None,
            amount=Decimal("5.00"),
            taxable=False,
            service=None,
            tax=authority,
        )
        block = block_of(invoice)

    assert block["tie_out"]["ties_out"] is False
    assert block["tie_out"]["authorities_total_display"] == "5.00"
    assert block["tie_out"]["tax_total_display"] == "9.00"
    assert Decimal(block["tie_out"]["delta"]) == Decimal("-4.00")
    # NOT adjusted: the authority still reports what its own lines say.
    assert block["authorities"][0]["subtotal_display"] == "5.00"


def test_tax_did_not_move_onto_services(brazos, marcus, bill):
    """PO 2026-08-11 — *"Tax rates are for bill not for service"* — UNTOUCHED.

    The per-SERVICE block must still hold every tax line in its one bill-level
    bucket. Two groupings of one immutable set of lines is the whole design; a
    re-attribution would put one service's money under another's heading while
    the GL stayed right.
    """
    with tenant_ctx(brazos):
        detail = billing_selectors.invoice_detail(bill["invoice"].id)

    services = detail["charges_by_service"]
    assert "tax" in services["bill_level"]["kinds"]
    # The two tax lines are in the bill-level bucket and their money is there.
    assert Decimal(services["bill_level"]["subtotal_display"]) == Decimal("19.68")
    for row in services["services"]:
        assert row["service"] == "water"
        assert Decimal(row["subtotal_display"]) == Decimal("238.60")
    # And the per-authority block reports the same 19.68 on its own axis.
    assert detail["taxes_by_authority"]["tie_out"]["tax_total_display"] == "19.68"


# ══════════════════════════════════════════════════════════════════════════
# THE FINANCE HALF — the same derivation over a NAMED SET of bills
# ══════════════════════════════════════════════════════════════════════════
def test_the_finance_read_answers_over_exactly_the_bills_it_is_given(brazos, marcus, bill):
    """The BOOKS choose the bills; billing only splits them.

    A period read written inside billing would have had to decide whether a
    VOID or CORRECTED bill's tax still belongs on a return — an unsigned money
    rule. This function is handed ids and asks nothing about them, which is why
    it can be right without that ruling existing.
    """
    with tenant_ctx(brazos):
        answer = billing_selectors.tax_by_authority_for_invoices([bill["invoice"].id])

    rows = {row["authority"]: row for row in answer["authorities"]}
    assert set(rows) == {BEXAR, TEXAS}
    assert rows[BEXAR]["subtotal_display"] == "4.77"
    assert rows[TEXAS]["subtotal_display"] == "14.91"
    assert answer["invoice_count"] == 1
    assert answer["currency"] == "USD"
    for row in rows.values():
        assert Decimal(row["subtotal_display"]) > Decimal("0")


def test_the_finance_read_is_empty_for_no_bills_and_never_zero_rows(brazos, marcus):
    """An empty id set is an empty answer — not a table of zeros to file from."""
    with tenant_ctx(brazos):
        assert billing_selectors.tax_by_authority_for_invoices([]) == {
            "currency": None,
            "authorities": [],
            "invoice_count": 0,
        }


def test_the_finance_read_is_tenant_scoped(brazos, lonestar, marcus, bill):
    """Hard rule 1 — another tenant's invoice id is simply not found."""
    with tenant_ctx(lonestar):
        answer = billing_selectors.tax_by_authority_for_invoices([bill["invoice"].id])
    assert answer["authorities"] == []
    assert answer["invoice_count"] == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-1190 closure (PO ruling 2026-08-31) + B4 §4.4 ❄️ + B4's 2026-08-11
#         sum-over-lines ruling + BR-BIL-069 + BR-BIL-010
# generated: 2026-08-31 by the OQ-1190/OQ-1171 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST by making `_taxes_by_authority` sum the STORED amounts
#        and round once — `AssertionError: assert '100.00' == '99.99'` on
#        test_the_rounding_follows_the_signed_reading, quoted in the lane report.
#        golden-verify 33 PASS / 0 FAIL before and after.
# exceptions: the two stamped GL uuids are literals rather than rows of a real
#        chart — this file asserts that the STAMP is read back unchanged, and
#        `_taxes_by_authority` resolves the account's label through the ledger
#        seam, which answers `None` for an id no chart holds. That null is the
#        contract's own documented fallback and is not what these cases assert.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
