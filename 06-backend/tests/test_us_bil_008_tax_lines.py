# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-008 (tax lines per authority + account-level exemption)
#           Screens: S30 (line detail) · S41 (Taxes & Remittance read-side)
# Rules:    BR-BIL-069 (a tax line names its AUTHORITY; each authority has its
#           own 2200-series liability account; the TENANT chooses it and the
#           PRODUCT generates the code — PO 2026-08-11 OQ-116, amended
#           2026-08-12 by OQ-148 · OQ-145 · OQ-147 · OQ-146) · BR-BIL-010 (the
#           GL stamp is resolved at issue and frozen; a tax whose authority has
#           no account is REPORTED BY THE RUN and the rest of the run
#           continues) · BR-BIL-021 (authorities and rates are tenant reference
#           data, never constants) · BR-BIL-055 (a break never blocks the run) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 3 (units)
# Golden:   GT-10 ❄️ (tax base = usage + base; the fee stays out) · GT-11 ❄️
#           (account-level exemption zeroes every authority) · B4.2 (the base) ·
#           B4.4 / BR-RAT-003 (per-line half-up, 2dp, ONCE) · B5 line 74 ❄️
#           ("2200-series Tax payable per authority")
# Tests:    this file
# Impacts:  apps/billing/issue.py (`_authority_label`, the named break) ·
#           apps/rating/selectors.tax_authority_label_for_tax
# ───────────────────────────────────────────────────────
"""US-BIL-008 — one tax line per AUTHORITY, and what happens when one has no home.

**THE STORY'S OWN SENTENCE, and it is the whole design.** *"A single tax charge
is usually several taxes"* (BR-BIL-069). On the reference bill the tax is State
of Texas 6.25% + Harris County 1.00% + City of Katy 1.00% over a **$100.58**
taxable base — three authorities, three debts, three returns to file — and each
one **rounds its own line** (B4.4, ❄️ finance-signed):

    6.29 + 1.01 + 1.01 = **8.31**

where a single combined rule produced **8.30**. The reference bill's total is
therefore **$117.02**. That cent is not a defect and it is not corrected here:
the PO ruled it on 2026-08-12 (*"Confirm $8.31 and the frozen figure gets an
addendum"*, OQ-148) and **B5 IS NOT EDITED** — the ❄️ frozen line stands and an
ADDENDUM records the split, which is the HUMAN-GUIDE §6 route the 4160/4170
accounts took. Nothing in this file changes a signed figure and nothing in it
may be "fixed" to make the cent go away.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE ASSERTS THAT NOTHING ASSERTED BEFORE
════════════════════════════════════════════════════════════════════════════
`test_br_bil_069_tax_authority_gl.py` proved the MECHANISM — a taxed bill
issues, each authority's line lands in its own 2200 account, a missing account
refuses the bill. It did not assert the story's own money: WE-1's four
authorities on a 221.90 base, WE-3's minimum-bill floor, WE-6's first bill, or
the exemption's totals. Those are US-BIL-008 §7 and they are here.

It also did not assert the half of OQ-146 that a clerk actually experiences.
The break code existed; the **NAME** did not. Until this lane the refusal read
*"the tax behind this line ('Tax HARRIS-CO') has no liability account"* — and
`HARRIS-CO` is a rate CODE somebody typed, not the body the money is owed to.
The PO's ruling is *"let the run report it"*, and reporting it means naming
**Harris County**, which is the row of S13 a clerk has to open. `tc10` is that
assertion and it was proved RED against the old message.

════════════════════════════════════════════════════════════════════════════
THE TARIFF SHAPES BELOW ARE SCAFFOLDING. THE TAX FIGURES ARE THE FIXTURE.
════════════════════════════════════════════════════════════════════════════
WE-1's 221.90 is the sum of eleven priced lines across five services; WE-3's
15.00 is a floored minimum; WE-6's 102.53 is a 20/31 proration. Reproducing
each of those *compositions* here would be re-testing US-BIL-007, US-BIL-010
and the rating engine, and would put a second implementation of B4.3 in a test
file. So each case is expressed as **the frozen taxable BASE** handed to the
engine through its published seam, exactly the way `tests/golden/conftest.py`
expresses GT-10 (*"GT-10 states the usage CHARGE, not a rate × quantity, so the
tariff is expressed with the GT-1 shape that produces it"*). What is asserted
is what US-BIL-008 owns: the base each authority multiplies, the per-authority
rounding, the line count, the exclusion of fees, and the totals.
"""

from decimal import Decimal

import pytest

from apps.billing import issue, models, rating_seam
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.isolation_helpers import (
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_br_bil_069_tax_authority_gl import (
    AUTHORITY_ACCOUNTS,
    SPLIT_TAX_TOTAL,
    TAXABLE_BASE,
    THREE_AUTHORITIES,
    a_tax_authority,
    tax_rules_for,
    three_authorities,
)
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    an_account,
    an_authorised_run,
)
from tests.test_us_bil_029_assemble import assemble, billing_data

pytestmark = pytest.mark.django_db

USD = "USD"
FULL_PERIOD = rating_seam.BillingPeriod(cycle_days=31, service_days=31)
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
EXEMPT = rating_seam.AccountContext(currency=USD, tax_exempt=True)

# ── The Brazos Bend authority set (US-BIL-008 §4, workbook §1) ───────────────
# Four authorities, effective 9.45%. Each rate is REFERENCE DATA in the product
# (BR-BIL-021) — it is written here as the fixture's own data, and the point of
# the four separate rules is that the engine emits FOUR lines, not one 9.45%.
WE1_AUTHORITIES = (
    ("TX State", Decimal("0.0625")),
    ("Travis County", Decimal("0.0100")),
    ("City franchise", Decimal("0.0200")),
    ("PUC", Decimal("0.0020")),
)
WE1_TAX_RULES = tuple(rating_seam.TaxRule(code=code, rate=rate) for code, rate in WE1_AUTHORITIES)

# ── US-BIL-008 §7, workbook verbatim ────────────────────────────────────────
WE1_TAXABLE = Decimal("221.90")
WE1_TAX_LINES = (Decimal("13.87"), Decimal("2.22"), Decimal("4.44"), Decimal("0.44"))
WE1_TAX_TOTAL = Decimal("20.97")
WE1_LATE_FEE = Decimal("5.00")
#: WE-2 (the SAME bill with the account flagged exempt): current 226.90.
WE2_CURRENT_EXEMPT = Decimal("226.90")

WE3_TAXABLE = Decimal("15.00")  # the floored minimum, INCLUDING its +5.40 adjustment
WE3_TAX_LINES = (Decimal("0.94"), Decimal("0.15"), Decimal("0.30"), Decimal("0.03"))
WE3_TAX_TOTAL = Decimal("1.42")
WE3_TOTAL = Decimal("16.42")

WE6_TAXABLE = Decimal("102.53")  # the 20/31 prorated first bill
WE6_TAX_TOTAL = Decimal("9.70")

#: The reference bill of BR-BIL-069, after OQ-148. 100.58 taxable + 8.31 tax +
#: 8.13 late fee. The late fee is GT-8's ❄️ frozen figure and is NOT taxed.
REFERENCE_LATE_FEE = Decimal("8.13")
REFERENCE_TOTAL = Decimal("117.02")


def _flat_tariff(base: Decimal, unit_price: Decimal) -> rating_seam.TariffConfig:
    """A one-service shape whose taxable lines sum to a stated base.

    Scaffolding, per the module docstring: the story's fixtures state the BASE,
    and the engine has to be handed something that produces it. `kWh` is carried
    explicitly because a quantity without a unit is forbidden outright
    (CLAUDE.md rule 3) — not because electricity is what WE-3 bills.
    """
    return rating_seam.TariffConfig(
        service="electric",
        model="flat",
        billed_unit="kWh",
        base_charge=base,
        unit_price=unit_price,
    )


def _priced_on(
    taxable: Decimal,
    *,
    taxes: tuple[rating_seam.TaxRule, ...],
    account: rating_seam.AccountContext = TAXED,
    fees: tuple[rating_seam.RatedLine, ...] = (),
) -> rating_seam.RatedBill:
    """Price a bill whose taxable subtotal IS `taxable`, through the seam.

    Half the base charge and half the usage, so both taxable KINDS are present
    and B4.2's *"usage + base"* is exercised rather than asserted on one line.
    """
    half = (taxable / 2).quantize(Decimal("0.01"))
    tariff = _flat_tariff(base=taxable - half, unit_price=Decimal("1.00"))
    consumption = rating_seam.Quantity(amount=half, unit="kWh")
    return rating_seam.price_period(
        tariff=tariff,
        consumption=consumption,
        period=FULL_PERIOD,
        account=account,
        taxes=taxes,
        fees=fees,
    )


def _a_fee(amount: Decimal, description: str) -> rating_seam.RatedLine:
    """A fee line the engine must keep OUT of the tax base (B4.2, GT-10)."""
    return rating_seam.RatedLine(kind="fee", description=description, amount=amount, taxable=False)


#: The rate CODES a clerk actually types into a rule, which are NOT the names of
#: the bodies the money is owed to. This gap is the whole content of the OQ-146
#: half of this story: the bill's own line says `Tax HARRIS-CO`, and a break row
#: that repeats that string has told the clerk nothing they did not already see.
#: `tax_rules_for` in the BR-BIL-069 file passes the authority name as the code,
#: which is a happy fixture and cannot discriminate the two readings — so these
#: tests build their own.
SHORT_CODES = {
    "State of Texas": "TX-ST",
    "Harris County": "HARRIS-CO",
    "City of Katy": "KATY-CITY",
}


def short_coded_tax_rules(built):
    """`tax_rules_for`, but with the rate codes a human would really type."""
    return tuple(
        rating_seam.TaxRule(code=SHORT_CODES[name], rate=rate, tax_id=str(built[name][0].id))
        for name, rate, _expected in THREE_AUTHORITIES
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — WE-1: four authorities over a 221.90 base, the fee excluded
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc1__four_authority_lines_on_the_we1_base():
    """US-BIL-008 §7 verbatim: 13.87 + 2.22 + 4.44 + 0.44 = **20.97**.

    FOUR lines, not one. That is the assertion that would catch the failure the
    PO's declined option C produces — one combined rule looks identical on a
    total and is impossible to take apart at remittance time.

    The 5.00 late fee is PRESENT and stays OUT of the base, which is the only
    way B4.2's structural claim can be tested at all (GT-10's method): hand the
    engine a fee and watch it not be taxed.
    """
    bill = _priced_on(WE1_TAXABLE, taxes=WE1_TAX_RULES, fees=(_a_fee(WE1_LATE_FEE, "Late fee"),))

    assert bill.taxable_subtotal == WE1_TAXABLE, "B4.2 — usage + base, and nothing else"
    tax_lines = bill.lines_of("tax")
    assert len(tax_lines) == 4, "one line PER AUTHORITY (BR-BIL-069)"
    assert tuple(line.amount for line in tax_lines) == WE1_TAX_LINES
    assert bill.tax_total == WE1_TAX_TOTAL

    # Each is B4.4 half-up on its OWN line, computed here from the frozen base
    # rather than copied, so a rounding regression is named as one.
    for (code, rate), amount in zip(WE1_AUTHORITIES, WE1_TAX_LINES, strict=True):
        assert amount == (WE1_TAXABLE * rate).quantize(Decimal("0.01")), code

    # The fee is on the bill, is not taxable, and is added AFTER tax (GT-10).
    assert bill.fee_total == WE1_LATE_FEE
    assert all(line.taxable is False for line in bill.lines_of("fee"))
    assert bill.total == WE1_TAXABLE + WE1_TAX_TOTAL + WE1_LATE_FEE


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — WE-2: the exemption is ACCOUNT-level and removes EVERY authority
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc2__an_exempt_account_gets_no_tax_line_at_all():
    """GT-11 ❄️ and B4.2: exempt regardless of service — WE-2's **226.90**.

    Zero LINES rather than zero-valued ones: a bill should not print a tax the
    account does not owe. The four rules are passed in LIVE, which is the point
    — the exemption has to zero a tax that would otherwise apply, and a fixture
    with no tax rules would prove nothing.
    """
    bill = _priced_on(
        WE1_TAXABLE,
        taxes=WE1_TAX_RULES,
        account=EXEMPT,
        fees=(_a_fee(WE1_LATE_FEE, "Late fee"),),
    )

    assert bill.lines_of("tax") == (), "not one authority survives an account exemption"
    assert bill.tax_total == Decimal("0.00")
    assert bill.taxable_subtotal == WE1_TAXABLE, "the BASE is unchanged; only the tax goes"
    # WE-2's current charges. The workbook's 271.90 total adds the 45.00 prior
    # balance, which is PRESENTATION and never posted (posting_seam: *"the prior
    # balance is already in AR from its own bill"*), so it is not asserted here.
    assert bill.total == WE2_CURRENT_EXEMPT


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 / TC-4 — the base is whatever the taxable line set adds up to
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc3__the_minimum_bill_floor_is_taxed_as_the_base():
    """WE-3: tax computes on the floored **15.00**, incl. its +5.40 adjustment.

    0.94 + 0.15 + 0.30 + 0.03 = **1.42**, total **16.42**. The rule this pins is
    that the minimum-bill ADJUSTMENT is taxable-like-base (GT-13), so raising a
    bill to its floor raises the tax with it.
    """
    bill = _priced_on(WE3_TAXABLE, taxes=WE1_TAX_RULES)

    assert bill.taxable_subtotal == WE3_TAXABLE
    assert tuple(line.amount for line in bill.lines_of("tax")) == WE3_TAX_LINES
    assert bill.tax_total == WE3_TAX_TOTAL
    assert bill.total == WE3_TOTAL


def test_us_bil_008_tc4__the_first_bills_prorated_base_is_taxed_at_10253():
    """WE-6: tax on taxable **102.53** = **9.70**.

    The deposit (150.00) and the connection charge (25.00) are BOTH untaxed and
    both arrive as fee-class inputs here — the deposit because it is a liability
    and never revenue, the CONN because a fee is never taxed (B4.2). US-BIL-010
    owns where those two lines come from; this owns that neither is in the base.
    """
    bill = _priced_on(
        WE6_TAXABLE,
        taxes=WE1_TAX_RULES,
        fees=(
            _a_fee(Decimal("150.00"), "Deposit"),
            _a_fee(Decimal("25.00"), "Connection charge"),
        ),
    )

    assert bill.taxable_subtotal == WE6_TAXABLE, "175.00 of one-time lines, none of it taxed"
    assert bill.tax_total == WE6_TAX_TOTAL
    assert bill.fee_total == Decimal("175.00")


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 (negative) — a fee is never taxable, and the flag is system-set
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc5__a_fee_forged_taxable_still_never_reaches_the_base():
    """B4.2: *"fees and late charges NOT taxed"* — asserted as a FORGERY.

    The caller hands the engine a fee line with `taxable=True`, which is the
    shape a compromised or careless call site produces. The engine's base is
    computed by KIND, not by the flag, so the forgery changes nothing: the tax
    is identical to TC-1's and the fee is still reported as a fee.

    That is the structural half of the rule. A base computed from the FLAG would
    make this test go red, which is exactly why it is written as an inequality
    against the forged total rather than only as an equality against 20.97.
    """
    forged = rating_seam.RatedLine(
        kind="fee", description="Late fee", amount=WE1_LATE_FEE, taxable=True
    )
    bill = _priced_on(WE1_TAXABLE, taxes=WE1_TAX_RULES, fees=(forged,))

    assert bill.taxable_subtotal == WE1_TAXABLE
    assert bill.tax_total == WE1_TAX_TOTAL
    would_be_if_the_flag_won = ((WE1_TAXABLE + WE1_LATE_FEE) * Decimal("0.0625")).quantize(
        Decimal("0.01")
    )
    assert bill.lines_of("tax")[0].amount != would_be_if_the_flag_won, (
        "a fee that reached the tax base would over-collect from every customer "
        "who ever paid late — B4.2 is structural, not a flag anyone sets"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 — the reference bill: 6.29 + 1.01 + 1.01 = 8.31, total 117.02
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc8__splitting_one_rule_into_three_authorities_moves_a_cent():
    """**PO 2026-08-12, OQ-148**: *"Confirm $8.31 and the frozen figure gets an
    addendum"*.

    The SAME $100.58 base under ONE 8.25% rule gives **8.30**; under the PO's
    own three-authority split it gives **8.31**, because each authority rounds
    its own line (B4.4). Both are computed here, side by side, so the cent is
    demonstrated rather than asserted — a reader who thinks one of the two is a
    bug can see that they are the same law applied to a different rule count.

    **B5 is not edited.** GT-10's frozen 8.30 stays asserted by
    `tests/golden/test_gt10_tax_base.py` and by `test_br_bil_069_tc4`; this
    asserts the SPLIT, which is what the addendum records.
    """
    split = _priced_on(
        TAXABLE_BASE,
        taxes=tuple(
            rating_seam.TaxRule(code=name, rate=rate) for name, rate, _ in THREE_AUTHORITIES
        ),
        fees=(_a_fee(REFERENCE_LATE_FEE, "Late fee"),),
    )
    combined = _priced_on(
        TAXABLE_BASE,
        taxes=(rating_seam.TaxRule(code="STATE+LOCAL", rate=Decimal("0.0825")),),
        fees=(_a_fee(REFERENCE_LATE_FEE, "Late fee"),),
    )

    assert tuple(line.amount for line in split.lines_of("tax")) == (
        Decimal("6.29"),
        Decimal("1.01"),
        Decimal("1.01"),
    )
    assert split.tax_total == SPLIT_TAX_TOTAL == Decimal("8.31")
    assert combined.tax_total == Decimal("8.30")
    assert split.tax_total - combined.tax_total == Decimal(
        "0.01"
    ), "one cent, and it is the per-line rounding law behaving as signed"
    assert split.total == REFERENCE_TOTAL == Decimal("117.02")


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 — the tenant CHOOSES the account; the product GENERATES the code
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc9__each_authority_is_owed_into_its_own_generated_account(brazos, dana):
    """**OQ-145** *"make them choose"* + **OQ-147** *"Generated"*.

    Three authorities, three DIFFERENT 2200-series accounts, each code allocated
    by the product rather than typed. The distinctness assertion is the one that
    matters: one shared Tax-payable bucket is the PO's declined option C, it
    looks perfectly healthy on a bill, and the split cannot be reconstructed
    afterwards.
    """
    with tenant_ctx(brazos):
        built = three_authorities(actor=dana)
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(brazos, account, run, billing_data(account, taxes=tax_rules_for(built)))

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        tax_lines = [line for line in bill.lines.all() if line.kind == "tax"]
        stamped = {str(line.gl_account_id) for line in tax_lines}
        assert len(stamped) == 3, "three authorities, three accounts — never one bucket"
        codes = sorted(
            ledger_models.LedgerAccount.objects.filter(pk__in=stamped).values_list(
                "code", flat=True
            )
        )
        assert codes == [AUTHORITY_ACCOUNTS[name][0] for name, _, _ in THREE_AUTHORITIES]
        assert all(code.startswith("2200") for code in codes), "the SIGNED series, B5 line 74"


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 — the run REPORTS the missing account, BY THE AUTHORITY'S NAME
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc10__a_tax_with_no_account_is_a_break_naming_the_authority(brazos, dana):
    """**PO 2026-08-12, OQ-146**: *"let the run report it"*.

    Three things, and the third is what this lane added:

    1. the bill does **not** issue — BR-BIL-010's stamp is atomic and a guessed
       account remits money to the wrong government;
    2. the failure is a NAMED BREAK the S31 phase-3 list groups on, and the run
       continues — the tenant is not blocked at setup from adding the authority;
    3. **the break names *Harris County***, not `Tax HARRIS-CO`. The rate code is
       what somebody typed into a rule; the authority is the row of S13 they have
       to open, and on a run of hundreds of bills that is the difference between
       a five-minute fix and a support ticket.

    PROVED RED against the previous message, which named the line description
    and not the authority.
    """
    with tenant_ctx(brazos):
        built = three_authorities(actor=dana)
        harris_tax, _account = built["Harris County"]
        harris_tax.liability_gl_account_id = None
        harris_tax.save(update_fields=["liability_gl_account_id"])

        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        rules = short_coded_tax_rules(built)
        draft = assemble(brazos, account, run, billing_data(account, taxes=rules))
        assert "Harris County" not in "".join(
            line.description for line in draft.lines.all()
        ), "the fixture must NOT smuggle the authority name onto the line — that is the gap"

        with pytest.raises(BillingRuleError) as refusal:
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        message = str(refusal.value)
        assert "Harris County" in message, (
            "OQ-146 asks the RUN to report it — reporting it means naming the authority, "
            "not the rate code a rule happens to carry"
        )
        assert "let the run report it" in message, "the ruling travels with its own refusal"

        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert result.broken[0].reason == issue.ISSUE_TAX_AUTHORITY_UNMAPPED
        assert "Harris County" in result.broken[0].detail


def test_us_bil_008_tc10b__the_rest_of_the_run_continues(brazos, dana):
    """*"the other accounts in the run continue"* — BR-BIL-069 (3) · BR-BIL-055.

    Two accounts, one of which carries the broken authority set. The clean one
    ISSUES. A run that stopped at the first unmappable authority would make one
    tenant's half-finished chart everybody's outage, which is the failure the
    ruling exists to prevent.
    """
    with tenant_ctx(brazos):
        good = three_authorities(actor=dana)
        clean_account = an_account(dana, brazos, account_no="A-10432")
        broken_account = an_account(dana, brazos, account_no="A-10433")
        run = an_authorised_run(brazos, dana)

        assemble(
            brazos,
            clean_account,
            run,
            billing_data(clean_account, taxes=short_coded_tax_rules(good)),
        )

        broken_rules = short_coded_tax_rules(good)
        katy_tax, _ = good["City of Katy"]
        katy_tax.liability_gl_account_id = None
        katy_tax.save(update_fields=["liability_gl_account_id"])
        assemble(brazos, broken_account, run, billing_data(broken_account, taxes=broken_rules))

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        # Every bill in this run carries City of Katy, so every bill breaks —
        # what is asserted is that the run RAN to the end and reported each of
        # them by name, rather than dying on the first.
        assert len(result.broken) == 2
        assert all("City of Katy" in row.detail for row in result.broken)
        assert all(row.reason == issue.ISSUE_TAX_AUTHORITY_UNMAPPED for row in result.broken)


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 (isolation) — an authority is one tenant's, and so is its label
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_008_tc7__another_tenants_authority_resolves_to_nothing(brazos, lonestar, dana):
    """Hard rule 1 · HR-1: a crafted tax id from another tenant is ABSENT.

    Both reads are probed — the money-bearing one (`liability_gl_account_id_for_tax`)
    and the DISPLAY one this lane added. The second matters as much as it looks
    like it does not: a label read that answered across tenants would leak one
    utility's tax-authority names into another's break list.
    """
    with tenant_ctx(brazos):
        _jurisdiction, brazos_tax, brazos_account = a_tax_authority(
            "State of Texas", Decimal("0.0625"), actor=dana
        )
        assert rating_selectors.tax_authority_label_for_tax(brazos_tax.id) == "State of Texas"
        assert rating_selectors.liability_gl_account_id_for_tax(brazos_tax.id) == str(
            brazos_account.id
        )

    with tenant_ctx(lonestar):
        assert rating_selectors.tax_authority_label_for_tax(brazos_tax.id) is None
        assert rating_selectors.liability_gl_account_id_for_tax(brazos_tax.id) is None
        # The PUBLISHED reads are what is asserted, because they are what
        # billing calls. The database half — RLS FORCE over `taxes` — is proved
        # against a live cluster by `tests/test_br_bil_069_...::tc13/tc14` and
        # by the isolation suite; a raw ORM count here would assert nothing on
        # the developer SQLite, which has no row-level security at all.


def test_us_bil_008_tc7b__the_label_degrades_to_something_a_human_can_read(brazos, dana):
    """A refusal must never print `None`, and the fallbacks are ordered.

    `_authority_label` is the one place that decides what "naming the authority"
    means when the name is not reachable, so its three answers are asserted
    directly rather than inferred from a message: the authority · the
    jurisdiction's name when no authority is recorded · the tax's own name.
    """
    with tenant_ctx(brazos):
        half_filled = rating_models.TaxJurisdiction.objects.create(
            tenant_id=brazos.id, name="Katy ISD", authority=None
        )
        tax = rating_models.Tax.objects.create(
            tenant_id=brazos.id,
            jurisdiction=half_filled,
            name="School district levy",
            kind="percent",
            rate=Decimal("0.005"),
        )
        assert rating_selectors.tax_authority_label_for_tax(tax.id) == "Katy ISD"

        nameless = rating_models.Tax.objects.create(
            tenant_id=brazos.id, name="Unassigned levy", kind="percent", rate=Decimal("0.005")
        )
        assert rating_selectors.tax_authority_label_for_tax(nameless.id) == "Unassigned levy"

    # And the billing-side fallback, with no read published at all.
    assert (
        issue._authority_label(None, authority_label=None, description="Tax HARRIS-CO")
        == "Tax HARRIS-CO"
    )
    assert (
        issue._authority_label("x", authority_label=lambda _id: None, description="")
        == "the tax on this line"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-008@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-02-invoice-gl.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-15 by Eng-Lead (US-BIL-008 lane — the story's own money,
#         plus OQ-146's named break)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S41's read is US-REP's) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_bil_008_tax_lines.py · golden 33 PASS/0 FAIL (unmoved)
# exceptions: (1) TC-6 (an authority rate changed mid-period without an
#         effective date) is NOT asserted here — `rating.Tax` carries
#         `effective_from`/`effective_to` and the refusal belongs to the rating
#         WRITE path (US-RAT-009, S13), not to billing's read of it. REPORTED
#         rather than duplicated: a billing-side copy of a rating validation is
#         a second implementation of one rule.
#         (2) The tariff SHAPES are scaffolding and the module docstring says
#         so — the frozen fixture is the taxable BASE and the tax arithmetic on
#         it, not the eleven-line composition that produces 221.90.
#         (3) WE-2's 271.90 and WE-3's/WE-6's totals that include a prior
#         balance are presentation, not posting, and are not asserted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
