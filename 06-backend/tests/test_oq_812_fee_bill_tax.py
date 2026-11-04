# ── Trace ──────────────────────────────────────────────
# Change:  One-time bill build plan task B7 (`04-docs/05-modules/07-billing/
#          12-one-time-bill-build-plan.md`) — a FEE BILL is taxed when its
#          charge code is marked taxable. Tests T1/T3 of the same plan.
# Ruling:  PO 2026-09-30, closing `OQ-812` with option (b), and the ❄️ B4.2
#          finance re-sign of the same day (decision log *"ONE-TIME BILL: SIX
#          ANSWERS"* (1); `04-docs/02-decisions/04-money-math-rules.md` ❄️
#          ADDENDUM 2026-09-30). Put as: *"Re-sign the frozen tax rule so a
#          Fee bill is taxed when its charge code is marked taxable?"* — PO
#          verbatim: *"Yes, re-sign."* Worked figure shown: **RECON $75.00
#          marked taxable at 8.25% → $81.19.**
# Rules:   B4.2 ❄️ (as re-signed 2026-09-30) · BR-RAT-062 / GT-17 ❄️ (ONE tax
#          pass per bill, over Σ rounded taxable lines) · BR-RAT-006 (exemption
#          is account-level) · BR-BIL-007 (the amount is the tenant's row) ·
#          CLAUDE.md rule 2 (4dp stored, rounded once at finalisation) · rule 7
# Code:    06-backend/apps/billing/fee_bill.py · apps/rating/engine.py
#          (`price_fee_bill`) · apps/billing/rating_seam.py (`price_fee_bill`)
# ───────────────────────────────────────────────────────
"""A fee bill raised on a TAXABLE charge code carries the account's tax.

⚠ **WHY THIS IS NOT UNDER `tests/golden/`.** A golden test there is keyed on a
finance-signed GT NUMBER (`G64` reads `test_gt<NN>_*.py` and the identity file
`10-scripts/gates/g64_engine_verified_gts.txt`), and B5's signed range is
GT-1..61. The fee-tax figure was re-signed on 2026-09-30 as a B4.2 ADDENDUM and
was given NO GT number, so filing it as `test_gt62_…` would mint a signed id
nobody signed. It is asserted here instead, against the exact figure the PO was
shown, so drift goes RED (CLAUDE.md, *"What counts as that sign-off"* (2)).

RED FIRST (hard-won law 7). Every case below was run against the tip before
`fee_bill.py` was changed; the verbatim failures are in the lane report and in
the review-ledger row. The two that matter:

  * `tc1` failed with `assert D('0') == D('6.19')` — the fee bill carried no
    tax at all, which is the absence `OQ-812` recorded and the PO ruled away.
  * `tc2` PASSED on the old code, and that is correct rather than a weak test:
    a non-taxable code must stay exactly as it was, so this is the case that
    proves the change did not tax every fee.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * `tc1` would pass over a fee bill that hard-coded 8.25%. `tc4` taxes the
    same fee at a SPLIT set of authorities (6.25% + 1.00% + 1.00%) and asserts
    one line per authority, rounded per line — which only the engine's own tax
    pass produces.
  * `tc1` would pass over a code path that taxed EVERY fee. `tc2` is the guard.
  * An exempt account taxed anyway would still pass `tc1`; `tc3` is the guard,
    and it uses the account's REAL exemption flag rather than a seam stub,
    because the fee bill used to read the flag off the wrong object.
  * A service-scoped tax (a City Franchise Fee on *electric only*) reaching a
    fee bill would still pass `tc1`; `tc5` is the guard — a fee bill has no
    services, so a tax scoped to one does not apply (DEF-273's fail-closed).
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import fee_bill
from apps.billing import models as billing_models
from apps.rating import models as rating_models

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_us_bil_001_prepare import (  # noqa: F401
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The day the fee is charged on — an argument, never a clock (BR-TEN-043).
FEE_ON = date(2026, 7, 9)
#: THE WORKED FIGURE PUT TO THE PO ON 2026-09-30, verbatim.
RECON = D("75.00")
RECON_TAX = D("6.19")  # 75.00 × 8.25% = 6.1875 → 6.19, half-up, once
RECON_TOTAL = D("81.19")


def _charge(tenant, code, *, taxable, amount=RECON):
    from apps.ledger import models as ledger_models

    gl = (
        ledger_models.LedgerAccount.objects.filter(
            tenant=tenant, deleted_at__isnull=True, code="4200"
        ).first()
        or ledger_models.LedgerAccount.objects.filter(
            tenant=tenant, deleted_at__isnull=True
        ).first()
    )
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": "Reconnection fee",
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": amount,
            "gl_account_id": gl.id,
            "taxable_default": taxable,
        },
    )
    return row


def _tax_on_plan(tenant, plan, *, rate, name, services=None):
    """One percent tax bound to the account's PLAN — where every tax lives."""
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=name, authority=name, level="state"
    )
    tax = rating_models.Tax.objects.create(
        tenant=tenant,
        jurisdiction=jurisdiction,
        name=name,
        kind="percent",
        rate=D(rate),
        applies_to_services=list(services) if services else None,
    )
    rating_models.PlanTaxRule.objects.create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )
    return tax


def _plan_of(account):
    from apps.metering import models as metering_models

    return metering_models.Unit.objects.get(pk=account.unit_id).rate_plan


def _lines(priced_bill):
    return {line.kind: line for line in priced_bill.priced.lines}


def test_oq812_tc1__a_taxable_recon_fee_is_75_plus_6_19_is_81_19(brazos, dana):
    """THE RE-SIGNED FIGURE: RECON $75.00 marked taxable at 8.25% → $81.19."""
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-81201", asset_no="M-81201")
        _tax_on_plan(brazos, _plan_of(account), rate="0.082500", name="Katy combined")
        _charge(brazos, "RECON-T", taxable=True)

        priced = fee_bill.price_charge_fee(
            account_id=str(account.id), charge_code="RECON-T", on_date=FEE_ON
        )

        assert priced.priced.tax_total == RECON_TAX
        assert priced.priced.total == RECON_TOTAL
        # B4.2 as re-signed — the base is the ROUNDED taxable fee line.
        assert priced.priced.taxable_subtotal == RECON
        kinds = [line.kind for line in priced.priced.lines]
        assert kinds == ["fee", "tax"], "the charge line first, then one line per authority"
        assert priced.line.kind == "fee" and priced.line.amount == RECON
        assert priced.line.taxable is True
        tax_line = _lines(priced)["tax"]
        assert tax_line.amount == RECON_TAX
        # BR-BIL-069 — the line names its authority, or issue cannot book it.
        assert tax_line.tax_id is not None


def test_oq812_tc2__a_code_not_marked_taxable_carries_no_tax(brazos, dana):
    """The guard against taxing EVERY fee: an unmarked code is exactly as before."""
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-81202", asset_no="M-81202")
        _tax_on_plan(brazos, _plan_of(account), rate="0.082500", name="Katy combined")
        _charge(brazos, "RECON-N", taxable=False)

        priced = fee_bill.price_charge_fee(
            account_id=str(account.id), charge_code="RECON-N", on_date=FEE_ON
        )

        assert [line.kind for line in priced.priced.lines] == ["fee"]
        assert priced.priced.tax_total == D("0")
        assert priced.priced.taxable_subtotal == D("0")
        assert priced.priced.total == RECON
        assert priced.line.taxable is False


def test_oq812_tc3__an_exempt_account_pays_no_tax_on_a_taxable_fee(brazos, dana):
    """B4.2 / BR-RAT-006 — exemption is account-level, on a fee bill too."""
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-81203", asset_no="M-81203")
        _tax_on_plan(brazos, _plan_of(account), rate="0.082500", name="Katy combined")
        _charge(brazos, "RECON-T", taxable=True)
        account.tax_exempt = True
        account.save(update_fields=["tax_exempt"])

        priced = fee_bill.price_charge_fee(
            account_id=str(account.id), charge_code="RECON-T", on_date=FEE_ON
        )

        assert priced.priced.tax_total == D("0")
        assert priced.priced.total == RECON
        assert [line.kind for line in priced.priced.lines] == ["fee"]


def test_oq812_tc4__one_tax_pass_one_line_per_authority_rounded_per_line(brazos, dana):
    """GT-17's shape on a fee bill: one pass, one line per authority.

    6.25% of 75.00 = 4.6875 → 4.69 · 1.00% = 0.75 · 1.00% = 0.75 → 6.19, the
    same $81.19 the PO was shown, reached through three authorities.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-81204", asset_no="M-81204")
        plan = _plan_of(account)
        _tax_on_plan(brazos, plan, rate="0.062500", name="State of Texas")
        _tax_on_plan(brazos, plan, rate="0.010000", name="Harris County")
        _tax_on_plan(brazos, plan, rate="0.010000", name="City of Katy")
        _charge(brazos, "RECON-T", taxable=True)

        priced = fee_bill.price_charge_fee(
            account_id=str(account.id), charge_code="RECON-T", on_date=FEE_ON
        )

        taxes = sorted(line.amount for line in priced.priced.lines if line.kind == "tax")
        assert taxes == [D("0.75"), D("0.75"), D("4.69")]
        assert priced.priced.tax_total == RECON_TAX
        assert priced.priced.total == RECON_TOTAL


def test_oq812_tc5__a_tax_scoped_to_a_service_does_not_reach_a_fee_bill(brazos, dana):
    """A fee bill has no services, so an *electric only* tax does not apply."""
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-81205", asset_no="M-81205")
        plan = _plan_of(account)
        _tax_on_plan(brazos, plan, rate="0.082500", name="Katy combined")
        _tax_on_plan(brazos, plan, rate="0.015000", name="City franchise", services=("electric",))
        _charge(brazos, "RECON-T", taxable=True)

        priced = fee_bill.price_charge_fee(
            account_id=str(account.id), charge_code="RECON-T", on_date=FEE_ON
        )

        assert [line.amount for line in priced.priced.lines if line.kind == "tax"] == [RECON_TAX]
        assert priced.priced.total == RECON_TOTAL


def test_oq812_tc6__the_draft_carries_the_tax_and_the_audit_row_says_so(brazos, dana):
    """The DRAFT is what the preview showed, and rule 7's row names the tax.

    The audit row is captured at the SINK, as `test_us_bil_012_one_time::tc5`
    does and for its reason: the shared fixtures replace the sink with a
    capture list, so reading `audit_log` back would assert the fixture's wiring
    rather than this module's write.
    """
    from core import audit as audit_kernel

    captured: list[dict] = []
    previous = audit_kernel._sink
    audit_kernel.set_audit_sink(captured.append)
    try:
        with tenant_ctx(brazos):
            account = a_one_time_account(brazos, dana, account_no="A-81206", asset_no="M-81206")
            _tax_on_plan(brazos, _plan_of(account), rate="0.082500", name="Katy combined")
            _charge(brazos, "RECON-T", taxable=True)

            invoice = fee_bill.raise_charge_fee(
                dana,
                account_id=str(account.id),
                charge_code="RECON-T",
                on_date=FEE_ON,
                due_days=21,
            )
            invoice.refresh_from_db()
            lines = list(billing_models.InvoiceLine.objects.filter(invoice=invoice))
    finally:
        audit_kernel.set_audit_sink(previous)

    assert invoice.bill_type == "fee"
    assert invoice.total == RECON_TOTAL
    assert invoice.tax_total == RECON_TAX
    assert sorted(line.amount for line in lines) == [RECON_TAX, RECON]
    drafted = [row for row in captured if row["action"] == "invoice.drafted"]
    assert len(drafted) == 1
    assert drafted[0]["entity_id"] == str(invoice.pk)
    assert drafted[0]["after"]["taxable"] is True
    assert D(drafted[0]["after"]["tax_total"]) == RECON_TAX
    assert D(drafted[0]["after"]["total"]) == RECON_TOTAL
