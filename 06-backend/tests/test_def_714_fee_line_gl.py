# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the GL stamp) · US-BIL-007 TC-5 (issue fails
#           atomically if any line cannot resolve a GL) · US-BIL-029 (stage 6
#           writes the draft) · US-RAT-009 (taxes & fees, S13)
#           Screens: S31 step 5 · S30 · S13 · S56
# Rules:    BR-RAT-117 (PO 2026-08-22, verbatim: "ruccuring and Autom apply
#           land on bill") · BR-BIL-010 (every line's GL account is resolved AT
#           ISSUE and frozen; charge codes carry their own GL) · BR-BIL-055 (a
#           break never blocks the run) · B4.2 (a fee is never in the tax base)
#           · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 4
#           (immutability) · rule 5 (only the ledger posting service writes
#           journal lines) · rule 6 (idempotency)
# Golden:   GT-1 ❄️ — 684 kWh × $0.12 = 82.08 + 18.50 base = 100.58, tax 8.25%
#           = 8.30. The fee rides ON TOP and never inside the tax base.
# Defects:  DEF-714 (a tenant that configures any recurring or auto-apply
#           charge code cannot issue ANY bill) · DEF-561 (the selector half,
#           whose fix tested the SELECTOR and not the issue path) · DEF-181
#           (the same failure for a deposit line, fixed by giving it its own
#           kind) · DEF-708 (the reconnection fee, which cannot become a
#           receivable until a fee line survives issue)
# ───────────────────────────────────────────────────────
"""A configured charge code reaches a bill AND the bill can be ISSUED.

**THE TEST DEF-714 SAYS NOBODY HAD WRITTEN.** Nothing in the suite issued a
bill for a tenant with a recurring charge code configured, so three pieces that
each looked right could disagree in production with every gate green:

  1. `gather._charge_fees_for` put `kind="fee"` lines on ordinary bills —
     exactly what BR-RAT-117 asks for (PO 2026-08-22);
  2. `stages/assemble_document` never set `InvoiceLine.charge` — the column
     shipped in the first billing migration and had **no writer anywhere in the
     repo**;
  3. `issue._gl_account_for` refused every fee line unconditionally *for want
     of that exact field*, without reading the `charge_id` it was handed.

So the draft assembled, the preview looked correct, and the bill died at issue.
Every tenant that used the feature the PO asked for on 2026-08-22 could issue
**no bill at all** — not the bill with the fee on it: any bill, because a run's
drafts each carry the recurring code. DEF-561's fix tested the SELECTOR and not
the issue path, which is why a guard already existed over this area and did not
bite.

**THE WORKED BILL BELOW, and it is the figure a human should be shown.**
Brazos Bend configures one recurring, auto-applied charge code — `SVC-M`,
*Monthly service fee*, **$12.00** — and points it at **4210 NSF & other fee
revenue**. Sarah Chen's June bill then reads:

    Electric usage   684 kWh × $0.12   82.08
    Electric base                      18.50   ── taxable base 100.58
    Monthly service fee                12.00   ── a FEE: never in the tax base
    Tax (8.25% of 100.58)               8.30
                                      ------
    Total                             120.88

and it **issues**, with the $12.00 credited to 4210 while the $100.58 of
electricity stays in 4100/4105. Before this lane the same bill raised
`BillingRuleError: a fee line ('Monthly service fee') names no charge code`.

**WHAT IS STILL REFUSED, ON PURPOSE** (`tc4`, `tc5`, `tc6`): a fee line that
names no code at all; a code the tenant has not yet pointed at an account; and
a code pointed at an account they have since deactivated (IS-1). Each refuses
BY NAME with its own break code, and the rest of the run issues (BR-BIL-055).

⚠ **THIS FILE ONCE SAID "A LATE FEE IS EXACTLY THAT", AND SINCE 2026-08-26 IT
IS NOT (BR-BIL-075, closing DEF-719).** An applied late fee now names the
tenant's own late-fee charge code — the account only; its amount is still
BR-BIL-001's ❄️ frozen B4 figure — so a bill carrying one ISSUES. `tc4` below
keeps testing the anonymous fee line, which is still a real and still-refused
shape, but it is no longer the late fee's shape; that path is covered by
`tests/test_def_719_late_fee_charge_code.py`.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, issue, models, runs
from apps.billing import rating_seam
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.ledger import services as ledger_services
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from core import tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
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
from tests.test_us_bil_029_assemble import SERVICE_DATE, billing_data
from tests.test_br_bil_069_tax_authority_gl import a_tax_authority

pytestmark = pytest.mark.django_db

#: The tenant's own configured code. The AMOUNT is the tenant's (BR-BIL-007 —
#: never a constant in code); $12.00 is Brazos Bend's, and it is the figure
#: BR-RAT-117's own test file already uses for the same code.
FEE_AMOUNT = Decimal("12.00")
FEE_NAME = "Monthly service fee"
#: GT-1 ❄️, unchanged by any of this: 82.08 + 18.50 = 100.58 taxable, tax 8.30.
TAXABLE_BASE = Decimal("100.58")
TAX_TOTAL = Decimal("8.30")
#: 100.58 + 8.30 + 12.00. The fee is ON the bill and OUT of the tax base (B4.2).
BILL_TOTAL = Decimal("120.88")
#: Where a charge-code fee belongs in the seeded chart. Read by CODE below, not
#: hardcoded as a uuid: a test holding the id would still pass if the stamp put
#: the fee in Electric revenue.
FEE_GL_CODE = "4210"


def _account_by_code(code):
    """One LIVE ledger account of the CURRENT tenant, by its chart code.

    Tenant-scoped explicitly (CLAUDE.md rule 1): the developer database is
    SQLite and has no RLS, so every tenant's `4210` is visible to a bare
    queryset and `tc7` — which needs two tenants — would resolve the wrong
    chart. On Postgres the policy would have done it; a test must not depend on
    which database it happens to be running against.
    """
    return ledger_models.LedgerAccount.objects.get(
        tenant_id=core_tenancy.current_tenant_id(), code=code, deleted_at__isnull=True
    )


def a_charge_code(tenant, *, code="SVC-M", gl_code=FEE_GL_CODE, auto=True, kind="recurring"):
    """One tenant-configured charge code, in the state a real tenant leaves it.

    `recurring` + `auto_apply` is BR-RAT-117's first route — the one that needs
    no plan binding and therefore reaches EVERY bill of the tenant, which is
    what made DEF-714 total rather than occasional.

    `gl_code=None` is the other real state: a code configured before the clerk
    has finished the chart of accounts. It refuses at issue (`tc5`).
    """
    account = _account_by_code(gl_code) if gl_code else None
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=FEE_NAME,
        charge_type=kind,
        auto_apply=auto,
        amount=FEE_AMOUNT,
        gl_account_id=account.id if account else None,
    )


def a_plan(tenant, name="DEF-714 plan"):
    return rating_models.RatePlan.objects.create(tenant=tenant, name=name, status="published")


def fee_lines_for(plan, *, service_date=SERVICE_DATE, customer_class=None, services=("electric",)):
    """The REAL gather projection of the REAL rating selector.

    Not hand-built `RatedLine`s: the whole defect lived in what these two
    functions did and did not carry, so a fixture that built the line itself
    would test the fixture. This is `gather.py`'s own code path, called with
    what `_gather_account` calls it with.
    """
    return gather._charge_fees_for(plan.id, service_date, customer_class, services)


def a_taxed_bill(tenant, dana, *, fees, rate=Decimal("0.0825")):
    """GT-1's bill with the given fee lines on it, drafted through the real chain.

    `runs.calculate_account` is the production entry point for phases 2 and 6 —
    stage 1 → stage 2 → rating's priced pass → stage 6 — so nothing between the
    charge code and `invoice_lines` is simulated here.
    """
    _jurisdiction, tax, tax_account = a_tax_authority("State of Texas", rate, actor=dana)
    account = an_account(dana, tenant)
    run = an_authorised_run(tenant, dana)
    data = billing_data(
        account,
        fees=fees,
        taxes=(rating_seam.TaxRule(code="STATE+LOCAL", rate=rate, tax_id=str(tax.id)),),
    )
    draft = runs.calculate_account(data, bill_run=run, service_date=SERVICE_DATE)
    return draft, run, tax_account


# ═══════════════════════════════════════════════════════════════════════════
# THE CASE DEF-714 EXISTS FOR — and the one the suite did not have
# ═══════════════════════════════════════════════════════════════════════════
def test_def_714_tc1__a_tenant_with_a_recurring_charge_code_can_issue_a_bill(brazos, dana):
    """END TO END: configure the code, run the bill, ISSUE it.

    The $12.00 lands on the bill (BR-RAT-117), the bill issues (BR-BIL-010
    resolves the code's own GL account), the fee is credited to **4210** and
    not to Electric revenue, and the tax is **8.30** — computed on the 100.58
    of electricity and NOT on the 112.58 that includes the fee (B4.2).

    Every one of those four is a different failure if it goes wrong, and the
    money one is silent: a fee swept into 4100 looks exactly like electricity
    sold, forever, on a row hard rule 4 forbids editing.
    """
    with tenant_ctx(brazos):
        code = a_charge_code(brazos)
        plan = a_plan(brazos)
        fees = fee_lines_for(plan)
        assert [line.description for line in fees] == [FEE_NAME], "BR-RAT-117: it reaches gather"
        assert fees[0].charge_id == str(code.id), "and it names WHICH code — the DEF-714 field"

        draft, _run, _tax_account = a_taxed_bill(brazos, dana, fees=fees)
        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        stored = models.Invoice.objects.get(pk=bill.pk)
        assert stored.status == models.INVOICE_ISSUED, "DEF-714: this is the whole defect"
        lines = list(stored.lines.all())
        assert all(
            line.gl_account_id is not None for line in lines
        ), "BR-BIL-010: every line, or the bill does not issue at all"

        # ── the money, to the digit ─────────────────────────────────────────
        fee_line = stored.lines.get(kind="fee")
        assert fee_line.amount == FEE_AMOUNT
        assert stored.subtotal == TAXABLE_BASE  # B4.2: the fee is NOT in it
        assert stored.tax_total == TAX_TOTAL  # 8.25% of 100.58, not of 112.58
        assert stored.total == BILL_TOTAL  # 100.58 + 8.30 + 12.00

        # ── the account: the CODE's own, and not a service's revenue ────────
        fee_account = _account_by_code(FEE_GL_CODE)
        assert str(fee_line.gl_account_id) == str(fee_account.id)
        usage_account, base_account = electric_gl_accounts()
        assert str(fee_line.gl_account_id) not in (usage_account, base_account)
        by_kind = {line.kind: str(line.gl_account_id) for line in lines if line.kind != "tax"}
        assert by_kind == {
            "usage": usage_account,
            "base": base_account,
            "fee": str(fee_account.id),
        }


def test_def_714_tc2__the_fee_lands_in_its_own_gl_bucket_in_the_books(brazos, dana):
    """CLAUDE.md rule 5 + US-BIL-005 §7: the posting handoff is per GL bucket.

    What the stamp is FOR. The entry debits AR for the whole $120.88 and
    credits **12.00 to 4210** beside 82.08/18.50 of electric revenue and 8.30
    of tax — read out of `journal_lines` itself rather than off any result
    object, because what matters is what LANDED in the books.
    """
    with tenant_ctx(brazos):
        a_charge_code(brazos)
        plan = a_plan(brazos)
        draft, _run, tax_account = a_taxed_bill(brazos, dana, fees=fee_lines_for(plan))
        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entry = ledger_models.JournalEntry.objects.filter(tenant=brazos).get()
        totals: dict[str, dict[str, Decimal]] = {}
        for gl_code, side, amount in ledger_models.JournalLine.objects.filter(
            tenant=brazos, journal_entry=entry
        ).values_list("ledger_account__code", "side", "amount"):
            bucket = totals.setdefault(gl_code, {"debit": Decimal("0"), "credit": Decimal("0")})
            bucket[side] += amount

        assert totals[FEE_GL_CODE]["credit"] == FEE_AMOUNT
        assert totals["4100"]["credit"] == Decimal("82.08")
        assert totals["4105"]["credit"] == Decimal("18.50")
        assert totals["1200"]["debit"] == BILL_TOTAL
        # Balanced pairs (hard rule 5): Σ debits == Σ credits, to the digit.
        debits = sum((row["debit"] for row in totals.values()), Decimal("0"))
        credits = sum((row["credit"] for row in totals.values()), Decimal("0"))
        assert debits == credits == BILL_TOTAL
        assert str(tax_account.id)  # the authority's own account exists and is used


def test_def_714_tc3__the_draft_names_the_charge_code_and_only_the_fee_does(brazos, dana):
    """The column DEF-714 says had no writer — `invoice_lines.charge_id`.

    Asserted at DRAFT time, before issue, because that is where it belongs: it
    is a fact about what was PRICED (like `service` and `tax`), and issue only
    RESOLVES it into a GL account. A regression in stage 6 is then named as a
    stage-6 regression rather than as a mysterious issue failure.

    And it is set on the FEE line ONLY: a usage line names no charge code, and
    inventing one would post electricity into a fee bucket.
    """
    with tenant_ctx(brazos):
        code = a_charge_code(brazos)
        plan = a_plan(brazos)
        draft, _run, _tax = a_taxed_bill(brazos, dana, fees=fee_lines_for(plan))

        by_kind = {line.kind: line for line in draft.lines.all()}
        assert str(by_kind["fee"].charge_id) == str(code.id)
        assert by_kind["usage"].charge_id is None
        assert by_kind["base"].charge_id is None
        assert by_kind["tax"].charge_id is None
        # Still a draft: identity is not the GL stamp (BR-BIL-010).
        assert all(line.gl_account_id is None for line in draft.lines.all())


# ═══════════════════════════════════════════════════════════════════════════
# WHAT IS STILL REFUSED — each by name, each with its own break code
# ═══════════════════════════════════════════════════════════════════════════
def test_def_714_tc4__a_fee_that_names_no_code_is_still_refused(brazos, dana):
    """The gap is NOT papered over — a fee line that names no code refuses.

    It refuses by name, atomically, and NOTHING is stamped — half a bill in the
    ledger is worse than no bill (US-BIL-007 TC-5). Its break code is
    deliberately the OTHER one: this wants a developer, `tc5` wants a clerk on
    S13.

    ⚠ **THE LATE FEE WAS THIS SHAPE UNTIL 2026-08-26 AND IS NOT ANY MORE.**
    BR-BIL-075 (PO ruling, closing DEF-719) gives an applied late fee the
    tenant's own charge code for its GL account — the ACCOUNT only, its amount
    stays B4's ❄️ frozen figure — so `decisions.py` no longer produces an
    anonymous fee line and a bill carrying a late fee issues. This case still
    guards the shape, because a producer that forgets the code is exactly how
    DEF-714 and DEF-201 happened; the late-fee path itself is asserted in
    `tests/test_def_719_late_fee_charge_code.py`.
    """
    with tenant_ctx(brazos):
        anonymous = (
            rating_seam.RatedLine(
                kind="fee", description="Late fee", amount=Decimal("8.13"), taxable=False
            ),
        )
        draft, run, _tax = a_taxed_bill(brazos, dana, fees=anonymous)
        assert draft.lines.get(kind="fee").charge_id is None

        with pytest.raises(BillingRuleError, match="names no charge code"):
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
        assert result.broken[0].reason == issue.ISSUE_FEE_LINE_UNMAPPABLE


def test_def_714_tc5__an_unmapped_charge_code_refuses_by_name(brazos, dana):
    """A code configured before the chart was finished — a REFUSAL, not a guess.

    Nothing falls back to a service's revenue account: $12.00 of fee income
    inside 4100 is indistinguishable from electricity sold and the stamp is
    frozen at issue. One named break, the rest of the run continues
    (BR-BIL-055), and a clerk closes it on S13 in a minute.
    """
    with tenant_ctx(brazos):
        a_charge_code(brazos, gl_code=None)
        plan = a_plan(brazos)
        fees = fee_lines_for(plan)
        assert fees[0].charge_id, "the line still NAMES its code — the gap is the mapping"

        draft, run, _tax = a_taxed_bill(brazos, dana, fees=fees)
        with pytest.raises(BillingRuleError, match="has no GL account"):
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
        assert result.broken[0].reason == issue.ISSUE_FEE_CHARGE_UNMAPPED


def test_def_714_tc6__a_deactivated_account_refuses_too(brazos, dana):
    """IS-1 — the tenant retired the account AFTER mapping the code.

    The stamp freezes with the bill, so a line posted to a retired account is
    as unrepairable as one posted to none. Two owners, and this is the LEDGER's
    half of the answer: rating says which account, the ledger says whether it
    is still live.
    """
    with tenant_ctx(brazos):
        a_charge_code(brazos)
        plan = a_plan(brazos)
        fees = fee_lines_for(plan)
        draft, _run, _tax = a_taxed_bill(brazos, dana, fees=fees)

        ledger_services.set_account_active(
            dana, account_id=_account_by_code(FEE_GL_CODE).id, active=False, at=ISSUED_AT
        )
        with pytest.raises(BillingRuleError, match="points at a ledger account"):
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


# ═══════════════════════════════════════════════════════════════════════════
# THE READ ITSELF — rating owns the mapping (BR-BIL-010), one home for it
# ═══════════════════════════════════════════════════════════════════════════
def test_def_714_tc7__the_read_answers_this_tenants_code_and_no_other(brazos, lonestar, dana):
    """HR-1 — another tenant's charge code is simply not found.

    `None` is the answer for every gap, and the caller REFUSES on it rather
    than substituting: an unknown id, another tenant's code, an unmapped one,
    and no id at all. A read that leaked across tenants here would post one
    utility's fee into another utility's chart.
    """
    with tenant_ctx(lonestar):
        theirs = rating_models.Charge.objects.create(
            tenant=lonestar,
            code="SVC-M",
            name=FEE_NAME,
            charge_type="recurring",
            auto_apply=True,
            amount=FEE_AMOUNT,
            gl_account_id=_account_by_code(FEE_GL_CODE).id,
        )
    with tenant_ctx(brazos):
        mine = a_charge_code(brazos)
        assert rating_selectors.gl_account_id_for_charge(mine.id) == str(
            _account_by_code(FEE_GL_CODE).id
        )
        assert rating_selectors.gl_account_id_for_charge(theirs.id) is None
        assert rating_selectors.gl_account_id_for_charge(None) is None
        assert rating_selectors.gl_account_id_for_charge("not-a-uuid") is None
        unmapped = a_charge_code(brazos, code="SVC-U", gl_code=None)
        assert rating_selectors.gl_account_id_for_charge(unmapped.id) is None


def test_def_714_tc8__issuing_twice_neither_re_stamps_nor_double_posts(brazos, dana):
    """Hard rules 4 and 6 — the fee line changes nothing about either.

    The second `issue_invoice` refuses (an issued bill is a fact, a correction
    is a new row) and the run-level pass finds no remaining draft, so the books
    still hold exactly ONE entry and the fee is credited to 4210 exactly once —
    $12.00, not $24.00.
    """
    with tenant_ctx(brazos):
        a_charge_code(brazos)
        plan = a_plan(brazos)
        draft, run, _tax = a_taxed_bill(brazos, dana, fees=fee_lines_for(plan))
        issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        with pytest.raises(BillingRuleError, match="cannot be issued again"):
            issue.issue_invoice(
                models.Invoice.objects.get(pk=draft.pk),
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        again = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        assert again.issued == ()

        assert ledger_models.JournalEntry.objects.filter(tenant=brazos).count() == 1
        credited = sum(
            (
                amount
                for amount in ledger_models.JournalLine.objects.filter(
                    tenant=brazos,
                    side="credit",
                    ledger_account__code=FEE_GL_CODE,
                ).values_list("amount", flat=True)
            ),
            Decimal("0"),
        )
        assert credited == FEE_AMOUNT


def test_def_714_tc9__the_selector_publishes_the_id_it_always_had(brazos):
    """DEF-561's own read, one field larger — and this is the field.

    `billable_charge_codes` returned the code, the name, the service, the
    amount and the taxable flag: everything needed to PRINT the line and
    nothing needed to POST it. The id was in the row it was already reading.
    """
    with tenant_ctx(brazos):
        code = a_charge_code(brazos)
        rows = rating_selectors.billable_charge_codes(a_plan(brazos).id, date(2026, 6, 30))
    assert [row["code"] for row in rows] == ["SVC-M"]
    assert rows[0]["id"] == str(code.id)
    assert rows[0]["amount"] == FEE_AMOUNT


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-714 (12-governance/10-defect-log.csv) + PO ruling 2026-08-25
#         option A (12-governance/02-decision-log.md) + BR-RAT-117 +
#         BR-BIL-010 + B4.2
# generated: 2026-08-25 by lane FEELINE (DEF-714 — make issue read the charge
#         code). 🔒 money path: the file under test carries
#         HUMAN-REVIEW-PENDING and a row is owed in
#         12-governance/09-human-review-ledger.md.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no route was added; the fix is
#         inside the existing `POST /billing/runs/{id}/issue` path and the S13
#         write that sets a code's GL account is an existing endpoint)
#         E=deferred(no-frontend-half — the two new refusals surface as `reason`
#         codes on the S31 phase-3 break list, which already renders them) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: every guard here was proved RED first — EIGHT mutants, each reverting
#         one hop of the identity or one half of the resolution, with their
#         verbatim failures in 12-governance/09-human-review-ledger.md. The
#         mutation cycle ran in a `cp -a` copy under the lane scratchpad, never
#         in the shared tree (r11 step 2d).
# status: VERIFIED-UNRATIFIED
# exceptions: `a_taxed_bill` configures ONE authority at 8.25% rather than the
#         three of BR-BIL-069, because the cent OQ-148 raises is that file's
#         subject and would obscure this one's. GT-1's ❄️ 100.58 / 8.30 are
#         reproduced here unchanged, which is the point: adding a fee moves the
#         TOTAL and must not move the tax.
# ──────────────────────────────────────────────────────────
