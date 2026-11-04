# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the GL stamp) · US-BIL-007 TC-5 (issue fails
#           atomically if any line cannot resolve a GL) · US-BIL-029 (stage 6
#           writes the draft) · US-RAT-009 (taxes & fees, S13)
#           Screens: S30 · S31 · S13 · S56
# Rules:    BR-BIL-069 (a tax line names its AUTHORITY; each authority has its
#           OWN 2200-series liability account; the TENANT manages both — PO
#           ruling 2026-08-11 closing OQ-116) · BR-BIL-010 (every line carries
#           a GL account resolved at issue and frozen) · BR-BIL-067 (the same
#           tenant-managed shape, ruled hours earlier for revenue accounts) ·
#           BR-RAT-003 / B4.4 (round per line, half-up, 2dp, ONCE) ·
#           BR-TEN-037 (tax jurisdictions are tenant-entered) · CLAUDE.md
#           rule 1 (tenant scoping) · rule 2 (money) · rule 4 (immutability)
# Golden:   B5 line 74 ❄️ (*"2200-series Tax payable per authority — tenant
#           authorities mint their own"*) · GT-17/WE-1 and GT-24/WE-11 (the
#           per-authority splits B5 machine-verifies)
# ───────────────────────────────────────────────────────
"""Each tax authority is owed into its OWN account — and a bill can now issue.

**WHAT THIS FILE IS FOR.** Until 2026-08-11 no bill in this product could be
issued. Two facts were missing and the same rule needed both: a usage or base
line could not say which SERVICE it charged for (stage 6 never wrote it), and a
tax line could not say which AUTHORITY it was collected for (`invoice_lines`
had no such column). BR-BIL-010 resolves a GL account per line from exactly
those two facts, so it refused — correctly, because a guess remits the wrong
money to a tax authority. The PO closed it (OQ-116), verbatim:

    "For each atheority have separate account and tagging; but also ensure you
     allow Use to manage it since every utility may not have every account"

The end-to-end case below is the one that proves the product is unblocked: the
REAL chain — stage 1 → stage 2 → rating's priced pass → stage 6 → issue — on a
bill with usage + base + THREE tax lines, every line stamped, each tax line to
its own authority's 2200-series account.

────────────────────────────────────────────────────────────────────────────
THE ONE CENT: WHY THIS FILE ASSERTS $8.31 WHERE THE RULING SAYS $8.30
────────────────────────────────────────────────────────────────────────────
Read this before "fixing" the numbers below.

The ruling states the split as *State of Texas 6.25% = $6.29 + Harris County
1.00% = $1.01 + City of Katy 1.00% = $1.00*, totalling **$8.30** on a $100.58
base. **Two of those three cannot both be true.** Harris County and the City of
Katy levy the SAME 1.00% on the SAME $100.58, so under the ❄️ FROZEN per-line
rounding law (B4.4 / BR-RAT-003 — half-up, 2dp, per line) they are the same
number: 1.005800 → **$1.01** each. The split computes **6.29 + 1.01 + 1.01 =
$8.31**, and the reference bill totals **$117.02** rather than GT-10's frozen
$117.01.

That is the frozen law behaving exactly as signed, and **B5 already signs a
case that proves per-line-summed is the law** even when it disagrees with the
single-rate figure. WE-11 (= GT-24, machine-verified by
`10-scripts/03-golden-verify.py`, whose own `tax_lines()` is
`[r2(base * t) for t in TAX]`): taxable $115.50 → tax **$10.92**, stated as
7.22 + 1.16 + 2.31 + 0.23 — while the same 9.45% as ONE rate gives **$10.91**.
B5 signs the sum. WE-1, WE-3, WE-6, WE-9 and WE-12 happen to agree at both
precisions; WE-11 does not, and the signed figure is the sum.

So this file asserts what the signed law produces and **raises the discrepancy
rather than resolving it: OQ-148**. Nothing here changes B4.4, which would need
a finance re-sign through HUMAN-GUIDE §6 and never an inline edit. GT-10's
$8.30 / $117.01 remain frozen and remain asserted — by
`test_gt10_tax_base.py`, and by `tc4` below, which shows the SAME 8.25%
configured as ONE authority still produces them to the digit. The cent appears
only when one rule becomes three, and the fact that it appears at all is the
sentence finance should see written down.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY ASSERTED AS AN ABSENCE
────────────────────────────────────────────────────────────────────────────
`tc7` asserts that creating a jurisdiction mints NOTHING. That is not a design
this lane chose — it is the boundary of a ruling that does not settle whether
adding an authority should auto-mint its account (**OQ-145**). The test will go
RED the day someone implements auto-minting, which is exactly the moment a
human should be reading this paragraph.

The OTHER half of that sentence expired on 2026-08-12. It used to read *"and
which could not be built anyway until the suffix question (OQ-147) is
answered"*. **OQ-147 IS ANSWERED** — PO, verbatim: *"Generated"* — so nothing
has to invent a code any more: `create_tax_authority_account()` with no code
allocates the next one in the signed 2200 series (`tc8` below, and the full
allocation rules in `tests/test_us_led_005_gl_designations.py`).
"""

from decimal import Decimal

import pytest

from apps.billing import issue, models, rating_seam
from apps.billing.exceptions import BillingRuleError
from apps.ledger import chart as ledger_chart
from apps.ledger import models as ledger_models
from apps.ledger import services as ledger_services
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from core import errors

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    an_account,
    an_authorised_run,
    electric_gl_accounts,
)
from tests.test_us_bil_029_assemble import assemble, billing_data

pytestmark = pytest.mark.django_db

# ── The ruling's own worked bill (see the module docstring on the cent) ──────
TAXABLE_BASE = Decimal("100.58")  # GT-1: 684 kWh × 0.12 = 82.08 usage + 18.50 base
TEXAS = ("State of Texas", Decimal("0.0625"), Decimal("6.29"))
HARRIS = ("Harris County", Decimal("0.0100"), Decimal("1.01"))
KATY = ("City of Katy", Decimal("0.0100"), Decimal("1.01"))  # ruling says 1.00 — OQ-148
THREE_AUTHORITIES = (TEXAS, HARRIS, KATY)
#: 6.29 + 1.01 + 1.01. The ruling narrates 8.30; B4.4 produces this. OQ-148.
SPLIT_TAX_TOTAL = Decimal("8.31")

#: The 2200-series codes used below, TYPED EXPLICITLY — and after the OQ-147
#: ruling of 2026-08-12 that is a deliberate choice, no longer the only option.
#: The product now GENERATES these same three codes for a tenant that adds three
#: authorities in this order (asserted in `tests/test_us_led_005_gl_designations
#: .py`); this file keeps typing them so the end-to-end assertions below name a
#: fixed account per authority and do not move if allocation order ever changes.
AUTHORITY_ACCOUNTS = {
    "State of Texas": ("2200-01", "Tax payable — State of Texas"),
    "Harris County": ("2200-02", "Tax payable — Harris County"),
    "City of Katy": ("2200-03", "Tax payable — City of Katy"),
}


def a_tax_authority(name, rate, actor=None):
    """One tenant-entered authority, its tax, and its own 2200-series account.

    All three steps are the TENANT's, in the order a real one takes them: enter
    the jurisdiction (BR-TEN-037), mint the liability account (B5 line 74 —
    *"tenant authorities mint their own"*), then point the tax at it on S13.
    Nothing in the product does any of the three on the tenant's behalf.
    """
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant_id=_current_tenant_id(), name=name, authority=name
    )
    code, account_name = AUTHORITY_ACCOUNTS[name]
    account = ledger_services.create_tax_authority_account(
        code=code, name=account_name, actor=actor
    )
    tax = rating_models.Tax.objects.create(
        tenant_id=_current_tenant_id(),
        jurisdiction=jurisdiction,
        name=f"{name} sales tax",
        kind="percent",
        rate=rate,
        liability_gl_account_id=account.id,
    )
    return jurisdiction, tax, account


def _current_tenant_id():
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def three_authorities(actor=None):
    """The ruling's three, in its own order. Returns `{name: (tax, account)}`."""
    built = {}
    for name, rate, _expected in THREE_AUTHORITIES:
        _jurisdiction, tax, account = a_tax_authority(name, rate, actor=actor)
        built[name] = (tax, account)
    return built


def tax_rules_for(built):
    """The seam's `TaxRule`s, each carrying WHOSE tax it is (BR-BIL-069)."""
    return tuple(
        rating_seam.TaxRule(code=name, rate=rate, tax_id=str(built[name][0].id))
        for name, rate, _expected in THREE_AUTHORITIES
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE CASE THE WHOLE LANE EXISTS FOR
# ═══════════════════════════════════════════════════════════════════════════
def test_br_bil_069_tc1__a_taxed_bill_issues_with_every_line_stamped(brazos, dana):
    """END TO END, through the REAL chain, and this is the unblocking case.

    Before the PO's ruling this exact bill could not be issued at all: the
    usage and base lines named no service and the tax lines named no authority.
    Now the same run produces a bill where EVERY line resolves — usage to 4100,
    base to 4105, and each of the three tax lines to a DIFFERENT 2200-series
    account, which is the whole substance of *"For each atheority have separate
    account and tagging"*.

    The three account ids are asserted DISTINCT explicitly. That assertion is
    the one that would catch the failure mode the PO's declined option C
    produces — all three taxes swept into one shared Tax-payable bucket, which
    looks perfectly healthy on a bill and is impossible to take apart again at
    remittance time.
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
        stored = models.Invoice.objects.get(pk=bill.pk)
        assert stored.status == models.INVOICE_ISSUED

        lines = list(stored.lines.all())
        assert all(
            line.gl_account_id is not None for line in lines
        ), "BR-BIL-010: every line, or the bill does not issue at all"

        # ── the money: the ruling's figures, under B4.4's per-line rounding ──
        tax_lines = {line.description: line for line in lines if line.kind == "tax"}
        assert len(tax_lines) == 3, "one line per authority — three debts, three returns"
        for name, _rate, expected in THREE_AUTHORITIES:
            line = tax_lines[f"Tax {name}"]
            assert line.amount == expected, f"{name}: B4.4 half-up on {TAXABLE_BASE}"
        assert sum(line.amount for line in tax_lines.values()) == SPLIT_TAX_TOTAL
        assert stored.subtotal == TAXABLE_BASE

        # ── the accounts: each authority's OWN, and three DIFFERENT ones ─────
        stamped = {
            name: str(tax_lines[f"Tax {name}"].gl_account_id)
            for name, _rate, _expected in THREE_AUTHORITIES
        }
        for name, _rate, _expected in THREE_AUTHORITIES:
            assert stamped[name] == str(built[name][1].id), f"{name} → its own 2200 account"
        assert len(set(stamped.values())) == 3, (
            "three authorities, three accounts — one shared bucket is option C, which the "
            "PO declined precisely because the split cannot be reconstructed afterwards"
        )
        codes = {
            name: ledger_models.LedgerAccount.objects.get(pk=stamped[name]).code for name in stamped
        }
        assert codes == {
            "State of Texas": "2200-01",
            "Harris County": "2200-02",
            "City of Katy": "2200-03",
        }

        # ── and the rest of the bill is stamped too (the service half) ───────
        usage_account, base_account = electric_gl_accounts()
        by_kind = {line.kind: str(line.gl_account_id) for line in lines if line.kind != "tax"}
        assert by_kind == {"usage": usage_account, "base": base_account}


def test_br_bil_069_tc2__stage_6_writes_what_produced_each_line(brazos, dana):
    """The draft carries the identity BEFORE issue — that is where it belongs.

    `service` and `tax` are facts about what was PRICED, so they are stamped
    with the snapshot at draft time; issue only RESOLVES them into a GL account.
    Asserting it here rather than only end-to-end means a regression in stage 6
    is named as a stage-6 regression, not as a mysterious issue failure.
    """
    with tenant_ctx(brazos):
        built = three_authorities(actor=dana)
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(brazos, account, run, billing_data(account, taxes=tax_rules_for(built)))

        lines = list(draft.lines.all())
        for line in lines:
            if line.kind in ("usage", "base"):
                assert line.service is not None and line.service.code == "electric"
                assert line.tax_id is None, "a usage line names no tax"
            if line.kind == "tax":
                assert line.service_id is None, "tax is a BILL-level charge, not a service's"
                assert line.tax_id is not None
        stamped_taxes = {str(line.tax_id) for line in lines if line.kind == "tax"}
        assert stamped_taxes == {str(tax.id) for tax, _account in built.values()}
        # The draft is still a draft: identity is not the GL stamp (BR-BIL-010).
        assert all(line.gl_account_id is None for line in lines)


def test_br_bil_069_tc3__an_unmapped_authority_refuses_by_name(brazos, dana):
    """*"every utility may not have every account"* — so the gap is a REFUSAL.

    Two authorities mapped, the third not. The bill refuses ATOMICALLY
    (US-BIL-007 TC-5) with a break code a clerk's screen can group on, and NONE
    of the other lines is stamped — half a bill in the ledger is worse than no
    bill. Nothing falls back to a neighbouring authority's account, which is
    the whole reason this refuses instead of guessing: the money would be
    remitted to the wrong government.

    ⚠ Whether SETUP should have refused this earlier is **OQ-146**, raised and
    not chosen. This test asserts only what BR-BIL-010 already signs.
    """
    with tenant_ctx(brazos):
        built = three_authorities(actor=dana)
        # The City of Katy's clerk has not finished the chart yet.
        katy_tax = built["City of Katy"][0]
        katy_tax.liability_gl_account_id = None
        katy_tax.save(update_fields=["liability_gl_account_id"])

        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(brazos, account, run, billing_data(account, taxes=tax_rules_for(built)))

        with pytest.raises(BillingRuleError, match="has no liability account"):
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        untouched = models.Invoice.objects.get(pk=draft.pk)
        assert untouched.status == models.INVOICE_DRAFT
        assert all(line.gl_account_id is None for line in untouched.lines.all())

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert result.issued == ()
        assert result.broken[0].reason == issue.ISSUE_TAX_AUTHORITY_UNMAPPED


def test_br_bil_069_tc4__one_authority_still_reproduces_gt10_to_the_digit(brazos, dana):
    """The ❄️ frozen figures are untouched by any of this.

    GT-1/GT-10 configure the tax as ONE combined 8.25% rule, and that bill still
    prices tax **8.30** on a **100.58** base. Asserted here, on a REAL issued
    bill with a REAL 2200 account behind it, because the module docstring makes
    a claim about the cent and a claim needs a test: the cent appears when one
    rule becomes three (OQ-148), and NOT before.
    """
    with tenant_ctx(brazos):
        _jurisdiction, tax, tax_account = a_tax_authority(
            "State of Texas", Decimal("0.0825"), actor=dana
        )
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(
            brazos,
            account,
            run,
            billing_data(
                account,
                taxes=(
                    rating_seam.TaxRule(
                        code="STATE+LOCAL", rate=Decimal("0.0825"), tax_id=str(tax.id)
                    ),
                ),
            ),
        )
        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        stored = models.Invoice.objects.get(pk=bill.pk)
        tax_line = stored.lines.get(kind="tax")
        assert tax_line.amount == Decimal("8.30")  # B5 GT-10 ❄️
        assert stored.tax_total == Decimal("8.30")
        assert str(tax_line.gl_account_id) == str(tax_account.id)


# ═══════════════════════════════════════════════════════════════════════════
# THE TENANT MANAGES IT — nothing seeded, nothing overwritten
# ═══════════════════════════════════════════════════════════════════════════
def test_br_bil_069_tc5__no_2200_account_is_ever_seeded(brazos):
    """B5 line 74 ❄️: *"tenant authorities mint their own"*.

    Both halves. The CHART carries no 2200 row at all — seeding one would
    invent a tax authority no tenant created (BR-TEN-037), and there is no
    universal list: a Texas operator owes Texas, Harris County and Katy; a
    utility two states away owes none of them. And a PROVISIONED tenant, which
    has run the whole seed, has no 2200 account either.
    """
    assert not [row for row in ledger_chart.SEED_CHART if row.code.startswith("2200")]
    with tenant_ctx(brazos):
        assert not ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, code__startswith="2200"
        ).exists()


def test_br_bil_069_tc6__a_reseed_never_overwrites_the_tenants_mapping(brazos, dana):
    """*"a tenant's own mapping is never overwritten by any seed or re-seed"*.

    The BR-BIL-067 shape, applied to tax. The tenant mints 2200-01, maps their
    tax at it, and then a repair run re-seeds the whole chart — the mapping
    still points where the tenant put it, and the account itself is untouched.
    """
    with tenant_ctx(brazos):
        _jurisdiction, tax, account = a_tax_authority(
            "State of Texas", Decimal("0.0625"), actor=dana
        )
        before = (str(account.id), account.code, account.name)

        ledger_services.seed_chart_of_accounts(actor=dana)

        tax.refresh_from_db()
        assert str(tax.liability_gl_account_id) == before[0], "their pointer, not ours"
        account.refresh_from_db()
        assert (str(account.id), account.code, account.name) == before
        assert (
            ledger_models.LedgerAccount.objects.filter(
                tenant=brazos, code__startswith="2200"
            ).count()
            == 1
        ), "a re-seed adds no 2200 rows of its own"


def test_br_bil_069_tc7__adding_an_authority_mints_nothing_by_itself(brazos, dana):
    """AN ASSERTED ABSENCE — the boundary of a ruling, not a design choice.

    Whether adding an authority should AUTO-MINT its 2200-nn account, or the
    tenant should point it at one they pick, is **OQ-145** and is not this
    lane's to implement. What is no longer true is the second half this
    docstring used to carry — *"it could not be implemented either way today: an
    auto-mint has to invent a code"*. Since the OQ-147 ruling of 2026-08-12 the
    product DOES number a 2200 account on request; nothing calls it from the
    jurisdiction path, which is the absence asserted here.

    So creating a jurisdiction and a tax creates NO ledger account, and this
    test says so out loud. It goes RED the day someone adds auto-minting — the
    right moment for a human to check the ruling arrived first.
    """
    with tenant_ctx(brazos):
        before = ledger_models.LedgerAccount.objects.filter(tenant=brazos).count()
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="City of Katy", authority="City of Katy"
        )
        tax = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="Katy sales tax",
            kind="percent",
            rate=Decimal("0.0100"),
        )
        assert ledger_models.LedgerAccount.objects.filter(tenant=brazos).count() == before
        assert tax.liability_gl_account_id is None


def test_br_bil_069_tc8__the_product_numbers_the_2200_suffix(brazos):
    """OQ-147 IS RULED — PO 2026-08-12, verbatim: *"Generated"*.

    **This test used to pin the opposite.** Until 2026-08-12 asking for an
    account with no code raised a `NotImplementedError` citing it, because B5 line
    74 signs the SERIES and is silent on the suffix, and the prime directive
    forbids a lane choosing. The PO chose: the tenant adds an authority and the
    product allocates the next code in the signed series. The refusal is gone
    and the assertion is rewritten in place rather than deleted, so a revert to
    "make the clerk type it" goes RED here.

    Pairs with OQ-145, ruled the same day: the tenant CHOOSES which account a
    tax points at; where a new one is needed the product NUMBERS it. The full
    allocation rules — monotonic, gap-preserving, per tenant, and guaranteed by
    `uq_ledger_accounts_code` rather than by a read — are asserted in
    `tests/test_us_led_005_gl_designations.py`, next to the service that owns
    them.
    """
    with tenant_ctx(brazos):
        minted = ledger_services.create_tax_authority_account(name="City of Katy")
    assert minted.code == "2200-01"
    assert ledger_chart.is_tax_payable_code(minted.code)
    assert minted.type == ledger_chart.TAX_PAYABLE_TYPE
    assert minted.designation is None


def test_br_bil_069_tc9__a_tax_account_must_be_in_the_signed_2200_series(brazos):
    """The half B5 DOES sign is enforced; the half it does not is not invented.

    `2300` is the signed customer-deposit liability and `4100` is electric
    revenue. A tax authority landing in either is a liability filed under the
    wrong head — and under revenue it would inflate the utility's own income by
    money it is merely holding for a government.
    """
    with tenant_ctx(brazos):
        for code in ("2300", "4100", "1200"):
            with pytest.raises(errors.ValidationError):
                ledger_services.create_tax_authority_account(code=code, name="Nope")
        # And the series itself is accepted in whatever shape the tenant types.
        for code in ("2200", "2200-07", "2200.TX"):
            minted = ledger_services.create_tax_authority_account(code=code, name=f"Tax {code}")
            assert minted.code == code
            assert minted.type == ledger_chart.TAX_PAYABLE_TYPE
            assert minted.designation is None, (
                "option C — one shared tax_payable designation — was declined by the PO; "
                "a twelfth designation against the ruled eleven is not this lane's to add"
            )


def test_br_bil_069_tc10__minting_an_existing_code_returns_it_untouched(brazos, dana):
    """Rule 1 of the ledger's seed, applied here: a tenant's chart is theirs.

    A second call for the same code does not rename, re-type or duplicate the
    account — it answers the one that exists. That is what makes provisioning,
    a repair run and a clerk clicking twice all safe.
    """
    with tenant_ctx(brazos):
        first = ledger_services.create_tax_authority_account(
            code="2200-01", name="Tax payable — State of Texas", actor=dana
        )
        second = ledger_services.create_tax_authority_account(
            code="2200-01", name="SOMETHING ELSE ENTIRELY", actor=dana
        )
        assert str(second.id) == str(first.id)
        assert second.name == "Tax payable — State of Texas"
        assert (
            ledger_models.LedgerAccount.objects.filter(tenant=brazos, code="2200-01").count() == 1
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE PATH — a mapping is validated, and it is validated by the LEDGER
# ═══════════════════════════════════════════════════════════════════════════
def test_br_bil_069_tc11__a_tax_may_only_be_mapped_to_this_tenants_live_account(
    brazos, lonestar, dana
):
    """Ownership AND liveness, because a deferred-FK uuid proves neither.

    Three refusals and one acceptance, all through the real S13 write path:
    another tenant's account, a deactivated account, and a uuid that is nothing
    at all are each a field error naming the account; the tenant's own live
    account is stored. The check is `apps.ledger.services.account_is_live` —
    the same function tenancy validates a service revenue account through, so
    the two GL surfaces cannot drift on what "a usable account" means.
    """
    with tenant_ctx(lonestar):
        intruder = ledger_services.create_tax_authority_account(
            code="2200-01", name="Someone else's tax payable"
        )
    with tenant_ctx(brazos):
        mine = ledger_services.create_tax_authority_account(
            code="2200-01", name="Tax payable — State of Texas", actor=dana
        )
        retired = ledger_services.create_tax_authority_account(
            code="2200-09", name="Tax payable — retired", actor=dana
        )
        from django.utils import timezone

        retired.deleted_at = timezone.now()
        retired.save(update_fields=["deleted_at"])

        created = rating_services.create_tax(
            dana,
            {
                "name": "Texas sales tax",
                "kind": "percent",
                "rate": "0.0625",
                "jurisdiction": {"name": "State of Texas", "authority": "State of Texas"},
                "liability_gl_account_id": str(mine.id),
            },
        )
        assert created["liability_gl_account_id"] == str(mine.id)

        import uuid as uuid_module

        for bad in (intruder.id, retired.id, uuid_module.uuid4()):
            # PO 2026-10-03 on CR-008: after creation the account changes only
            # through Settings › Accounting's door, which validates the same way.
            with pytest.raises(errors.ValidationError) as raised:
                rating_services.set_tax_liability_account(
                    dana, created["id"], {"liability_gl_account_id": str(bad)}
                )
            assert raised.value.field_errors[0]["field"] == "liability_gl_account_id"
            assert raised.value.field_errors[0]["message_key"] == "rating.taxes.gl_account_unknown"

        # Unchanged by every refusal — nothing partial was written.
        assert rating_selectors.tax_row(rating_models.Tax.objects.get(pk=created["id"]))[
            "liability_gl_account_id"
        ] == str(mine.id)


def test_br_bil_069_tc12__the_rate_may_be_overridden_and_the_authority_still_travels(brazos, dana):
    """A plan `rate_override` changes WHAT IS CHARGED, never WHO IS OWED.

    `plan_tax_rules` used to skip the `taxes` lookup entirely when a rule
    carried an override — which would have made every overridden tax
    unbillable, because the line it produced could name no authority. The
    lookup is now unconditional and this is the test that keeps it that way.
    """
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="State of Texas", authority="State of Texas"
        )
        account = ledger_services.create_tax_authority_account(
            code="2200-01", name="Tax payable — State of Texas", actor=dana
        )
        tax = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="Texas sales tax",
            kind="percent",
            rate=Decimal("0.0625"),
            liability_gl_account_id=account.id,
        )
        plan = _a_plan(brazos)
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos,
            rate_plan=plan,
            jurisdiction=jurisdiction,
            rate_override=Decimal("0.0700"),
        )

        rules = rating_selectors.plan_tax_rules(str(plan.id))
        assert len(rules) == 1
        assert rules[0]["rate"] == Decimal("0.0700"), "the override is what is charged"
        assert rules[0]["tax_id"] == str(tax.id), "and the authority still travels"
        assert rating_selectors.liability_gl_account_id_for_tax(tax.id) == str(account.id)


def _a_plan(tenant):
    """The smallest rate plan `plan_tax_rules` can hang a rule off."""
    return rating_models.RatePlan.objects.create(
        tenant=tenant, name="Residential Standard", status="draft"
    )


def test_br_bil_069_tc13__a_tax_id_from_another_tenant_resolves_to_nothing(brazos, lonestar, dana):
    """The read is tenant-scoped, so a crafted id is simply not found.

    Not an error message distinguishing "not yours" from "does not exist" —
    that would answer a question the asker has no right to (the posture
    `apps/ledger/selectors.account_is_live` states for the same reason). `None`
    here becomes a REFUSAL at issue, never a stamped account.
    """
    with tenant_ctx(lonestar):
        their_account = ledger_services.create_tax_authority_account(
            code="2200-01", name="Their tax payable"
        )
        their_jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=lonestar, name="State of Texas", authority="State of Texas"
        )
        their_tax = rating_models.Tax.objects.create(
            tenant=lonestar,
            jurisdiction=their_jurisdiction,
            name="Texas sales tax",
            kind="percent",
            rate=Decimal("0.0625"),
            liability_gl_account_id=their_account.id,
        )
    with tenant_ctx(brazos):
        assert rating_selectors.liability_gl_account_id_for_tax(their_tax.id) is None
        assert rating_selectors.liability_gl_account_id_for_tax(None) is None
        assert rating_selectors.liability_gl_account_id_for_tax("not-a-uuid") is None


# ═══════════════════════════════════════════════════════════════════════════
# ISOLATION — the new column and the new accounts, at the DATABASE
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_br_bil_069_tc14__the_tagged_line_is_rls_scoped(rls, brazos, lonestar, dana):  # noqa: F811
    """`invoice_lines` gained a COLUMN and no table, so the guarantee comes from
    `invoice_lines_tenant_isolation` (billing/0002) — and a claim that an
    existing policy covers a new column is worth nothing until it is probed.

    Probed on the column itself: under the intruder's context the neighbour's
    tagged line is not there, and neither is the tax it names.
    """
    with live_tenant_context(brazos.id):
        built = three_authorities(actor=dana)
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = assemble(brazos, account, run, billing_data(account, taxes=tax_rules_for(built)))
        tagged = str(models.InvoiceLine.objects.filter(invoice=draft, kind="tax").first().id)
        texas_tax = str(built["State of Texas"][0].id)

    assert_rls_scoped(rls, "invoice_lines", owner=brazos, intruder=lonestar, owner_ids={tagged})
    with live_tenant_context(lonestar.id):
        assert rls.count("invoice_lines", "tax_id = %s", [texas_tax]) == 0
        assert rls.count("taxes", "id = %s", [texas_tax]) == 0
    assert_no_foreign_rows_anywhere(rls, lonestar, ("invoice_lines", "taxes", "ledger_accounts"))


@pytest.mark.isolation
@requires_postgres
def test_br_bil_069_tc15__minting_refuses_outright_with_no_tenant_context(
    rls, brazos
):  # noqa: F811
    """Deny-by-default. With `app.tenant_id` unset the policy hides every row and
    the service refuses before a query is built — a 2200 account belonging to
    nobody is not a thing to let happen quietly (CLAUDE.md rule 1)."""
    assert_denied_without_context(rls, "ledger_accounts", "taxes", "invoice_lines")
    with pytest.raises(errors.AuthError) as raised:
        ledger_services.create_tax_authority_account(code="2200-01", name="Tax payable")
    assert raised.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (sources, in order: 12-governance/02-decision-log.md
#         2026-08-11 row "EACH TAX AUTHORITY GETS ITS OWN LIABILITY ACCOUNT…" ·
#         12-governance/01-open-questions.md OQ-116 (CLOSED) + OQ-145/146/147/148 ·
#         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-069 +
#         BR-BIL-010 + BR-BIL-067 · 04-docs/02-decisions/05-golden-tests.md
#         line 74 ❄️ and WE-1/WE-11 · 04-docs/02-decisions/04-money-math-rules.md B4.4)
# generated: 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S13 write path is an existing
#         endpoint and no route was added) E=deferred(no-frontend-half) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: every guard here was proved RED first — the mutations and their verbatim
#         failures are in 12-governance/09-human-review-ledger.md
# exceptions: (1) `tc1` asserts 6.29 / 1.01 / **1.01** and a split total of
#         **8.31**, where the PO's ruling narrates 1.00 and 8.30. Two authorities
#         at the same rate on the same base cannot differ by a cent under the ❄️
#         FROZEN B4.4 per-line law, and B5's own WE-11 signs the per-line SUM
#         over the single-rate figure. RAISED as OQ-148, not resolved: changing
#         a signed figure needs a finance re-sign via HUMAN-GUIDE §6 · (2) `tc7`
#         asserts an ABSENCE (nothing auto-mints) and is designed to go RED when
#         OQ-145 is ruled · (3) the two -m isolation cases are Postgres-only and
#         SKIP with a vendor reason on sqlite, never a silent pass
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
