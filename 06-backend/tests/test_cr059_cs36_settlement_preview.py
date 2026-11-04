# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 §8 CS-36, task 20 — *"S30 Fix a bill: the settlement panel on
#           the preview: paid to date · what the rebill takes · what returns to
#           credit · what is still owed"*.
#           Screens: S30 (the Fix-a-bill preview, section 6)
# Rules:    BR-PAY-1072 (a restatement releases the allocations against the bill
#           it replaces) · BR-PAY-010 (the released money becomes carried credit
#           and the next issue draws it down) · BR-PAY-041 (a credit position is
#           SIGNED and never floored — a debt is a real debt, PO 2026-08-11) ·
#           BR-BIL-044 (the preview is the approval artifact; NINE sections and
#           this is inside section 6, not a tenth) · BR-BIL-072 (what a bill
#           ASKS for) · CLAUDE.md rule 2 (money as decimal strings)
# Tests:    this file
# Impacts:  apps/billing/corrections.settlement_preview · BillImpact.settlement ·
#           apps/billing/single_correction (section 6 carries it) ·
#           07-frontend/src/features/billing/FixABillTab.tsx (draws it)
# ───────────────────────────────────────────────────────
"""THE FOUR FIGURES A CLERK NEEDS BEFORE THEY CORRECT A BILL SOMEBODY PAID.

════════════════════════════════════════════════════════════════════════════
WHY A PANEL AND NOT A SENTENCE
════════════════════════════════════════════════════════════════════════════
The preview has carried a SENTENCE about this since the module was written —
*"payments allocated to the original re-allocate to the rebill; any excess
becomes a carried account credit"* — and CS-36's whole finding is that the
sentence was composed on every preview and executed by nobody until 2026-09-01.
The release is built now. This is the half that lets the clerk SEE what it will
do, in figures, before they commit (B14 rule 11).

**NOTHING IS COMPUTED ON A SCREEN.** S30 draws money it is given; a frontend
that subtracted the corrected total from a payment would be a second definition
of "settled", which is the exact shape of DEF-2416 one bill along.

════════════════════════════════════════════════════════════════════════════
THE THREE CASES ARE CS-36's OWN, AND THE FIGURES ARE ITS OWN
════════════════════════════════════════════════════════════════════════════
    down       100.00 paid, corrected to  80.00 → takes 80.00, credit 20.00,
                                                  owed 0.00
    up         100.00 paid, corrected to 120.00 → takes 100.00, credit 0.00,
                                                  owed 20.00
    part-paid   60.00 paid, corrected to  80.00 → takes 60.00, credit 0.00,
                                                  owed 20.00

The same three the release service is proved on (`test_cr059_cs36_restatement_pg`),
so the panel and the engine cannot describe different outcomes.

**RED PROVED FIRST (hard-won law 7).** Before `settlement_preview` existed,
every case here failed on `AttributeError: 'BillImpact' object has no attribute
'settlement'`; with a draft that floored a NEGATIVE credit position into the
available money, TC-5 failed `assert '20.00' == '0.00'` — a customer in
debt would have been shown that debt paying for their own replacement bill.

**THE SEAM IS NOT STUBBED** in four of the six cases: the figures come from
`apps.payments.billing_seam.allocated_so_far` and `apps.payments.credit.
account_credit_position`, resolved BY NAME, which is the wiring hard-won law 2
is about. The two that stub stub the seam ABSENT, which is what they are for.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.billing import corrections
from apps.billing.correction_models import CLASS_CREDIT_ONLY, CLASS_DOCUMENT, CLASS_RESTATEMENT
from apps.payments import models as payment_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_016_bulk_corrections import _RatedBill, _RatedLine, an_issued_bill
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)


def _a_cleared_payment(tenant, account, amount: Decimal, *, no: str = "PMT-000001"):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=no,
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
    )


def _allocate(tenant, payment, invoice, amount: Decimal):
    return payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=invoice, amount=amount
    )


def _corrected_bill(total: Decimal) -> _RatedBill:
    """The recomputation, supplied so this file prices nothing itself."""
    return _RatedBill(
        total=total,
        lines=(_RatedLine("usage", "Water usage", total),),
    )


def _impact(invoice, *, correction_class=CLASS_RESTATEMENT, corrected_total=Decimal("80.00")):
    return corrections.build_impact(
        invoice,
        reason_codes=("meter_read_error",),
        correction_class=correction_class,
        corrected=(
            _corrected_bill(corrected_total) if correction_class == CLASS_RESTATEMENT else None
        ),
        goodwill_amount=Decimal("25.00") if correction_class == CLASS_CREDIT_ONLY else None,
    )


def _settled(brazos, dana, *, paid: Decimal, corrected_total: Decimal, invoice_no: str):
    """One issued 100.00 bill with `paid` against it, previewed at `corrected_total`."""
    account = an_account(dana, brazos)
    run = a_run(brazos)
    invoice = an_issued_bill(brazos, account, run, invoice_no=invoice_no)
    invoice.total = Decimal("100.00")
    invoice.save(update_fields=["total"])
    if paid > Decimal("0"):
        payment = _a_cleared_payment(brazos, account, paid)
        _allocate(brazos, payment, invoice, paid)
    return _impact(invoice, corrected_total=corrected_total).settlement


# ═══════════════════════════════════════════════════════════════════════════
# CS-36's three shapes — the ones the release engine is proved on
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task20_tc1__corrected_DOWN__the_change_goes_back_as_credit(brazos, dana):
    """100.00 paid, corrected to 80.00: the replacement takes 80, 20 is credit.

    This is the customer the whole change request is about. Before the release
    existed his screen said he owed 80.00 and was six days late, while the books
    said the utility owed him 20.00.
    """
    with tenant_ctx(brazos):
        settlement = _settled(
            brazos, dana, paid=Decimal("100.00"),
            corrected_total=Decimal("80.00"), invoice_no="BL-2608-0141",
        )
        assert settlement is not None
        assert settlement["paid_to_date"] == "100.00"
        assert settlement["released"] == "100.00"
        assert settlement["rebill_takes"] == "80.00"
        assert settlement["returns_to_credit"] == "20.00"
        assert settlement["still_owed"] == "0.00"
        assert settlement["currency"] == "USD"


def test_cs36_task20_tc2__corrected_UP__the_difference_is_still_owed(brazos, dana):
    """100.00 paid, corrected to 120.00: 100 is taken, 20.00 stays owing."""
    with tenant_ctx(brazos):
        settlement = _settled(
            brazos, dana, paid=Decimal("100.00"),
            corrected_total=Decimal("120.00"), invoice_no="BL-2608-0142",
        )
        assert settlement["rebill_takes"] == "100.00"
        assert settlement["returns_to_credit"] == "0.00"
        assert settlement["still_owed"] == "20.00"


def test_cs36_task20_tc3__PART_PAID_needs_no_special_case(brazos, dana):
    """60.00 of 100.00, corrected to 80.00: 60 is taken and 20.00 is owed.

    CS-36 says this in terms — *"no special case"* — and the arithmetic here is
    the same three lines as the other two shapes. A branch on "was it paid in
    full" would be a second definition of settled, which is the defect.
    """
    with tenant_ctx(brazos):
        settlement = _settled(
            brazos, dana, paid=Decimal("60.00"),
            corrected_total=Decimal("80.00"), invoice_no="BL-2608-0143",
        )
        assert settlement["paid_to_date"] == "60.00"
        assert settlement["rebill_takes"] == "60.00"
        assert settlement["returns_to_credit"] == "0.00"
        assert settlement["still_owed"] == "20.00"


def test_cs36_task20_tc4__a_bill_NOBODY_paid_settles_at_zero_and_is_not_absent(brazos, dana):
    """0.00 paid is a MEASURED zero and not a missing panel.

    The read looked and found nothing applied; the whole corrected total is
    owed. `None` would say payments could not be asked, which is a different
    fact and DEF-127's own lesson.
    """
    with tenant_ctx(brazos):
        settlement = _settled(
            brazos, dana, paid=Decimal("0"),
            corrected_total=Decimal("80.00"), invoice_no="BL-2608-0144",
        )
        assert settlement is not None
        assert settlement["paid_to_date"] == "0.00"
        assert settlement["rebill_takes"] == "0.00"
        assert settlement["still_owed"] == "80.00"


# ═══════════════════════════════════════════════════════════════════════════
# The two boundaries — a DEBT, and a class that releases nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task20_tc5__a_NEGATIVE_credit_position_pays_for_nothing(brazos, dana):
    """A customer already in debt does not have that debt buy their new bill.

    `credit_position_for_account` is SIGNED and is deliberately not floored
    (BR-PAY-041, PO 2026-08-11 *"Yes, it's a real debt"*) — its own docstring
    says the CALLER decides that a debt settles nothing. This is that decision,
    asserted: the position is SHOWN as it is, and the money available to the
    replacement is the released amount alone.

    Built by refunding more than the account ever paid, which is exactly how
    the PO's own $57.13 debt arises after a bounce.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0145")
        invoice.total = Decimal("100.00")
        invoice.save(update_fields=["total"])
        payment = _a_cleared_payment(brazos, account, Decimal("100.00"))
        _allocate(brazos, payment, invoice, Decimal("100.00"))
        # A refund of 40.00 against an account whose whole 100.00 is applied
        # leaves the position at −40.00 (Σ payments − Σ allocations − Σ refunds).
        # `refunds` hangs off the PAYMENT, not the account — B2 §2 gives this
        # table no account column, which is `models.Refund`'s own OQ-167.
        payment_models.Refund.objects.create(
            tenant=brazos,
            payment=payment,
            amount=Decimal("40.00"),
            currency="USD",
            status=payment_models.REFUND_ISSUED,
            issued_at=POSTED_AT,
        )

        settlement = _impact(invoice, corrected_total=Decimal("80.00")).settlement

        # The debt is SHOWN — a panel that hid it would be a screen deciding
        # what a clerk may know about a customer's position.
        assert settlement["credit_on_account"] == "-40.00"
        # …and it buys nothing. Available is the released 100.00 alone.
        assert settlement["available"] == "100.00"
        assert settlement["rebill_takes"] == "80.00"
        assert settlement["returns_to_credit"] == "20.00"


@pytest.mark.parametrize("klass", [CLASS_CREDIT_ONLY, CLASS_DOCUMENT])
def test_cs36_task20_tc6__a_class_that_releases_NOTHING_has_no_settlement(brazos, dana, klass):
    """A concession and a document reissue move no bill, so nothing settles.

    CS-36 is explicit: *"a goodwill credit needs nothing at all, because no bill
    changed and no payment moved"*. `None` rather than a panel of zeroes — four
    zeroes would tell a clerk the customer's payment had been examined and found
    to be worth nothing.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0146")
        payment = _a_cleared_payment(brazos, account, Decimal("100.00"))
        _allocate(brazos, payment, invoice, Decimal("100.00"))

        assert _impact(invoice, correction_class=klass).settlement is None


def test_cs36_task20_tc7__an_unreachable_seam_is_None_and_never_zeroes(brazos, dana, monkeypatch):
    """Payments unreachable ⇒ no panel, never a panel of zeroes.

    `payments_seam.allocated_against_invoice` answers `None` for *nobody could
    ask*, and a settlement of 0.00 over that would tell a clerk the customer had
    paid nothing on a bill they may have settled in full.
    """
    from apps.billing import payments_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0147")
        payment = _a_cleared_payment(brazos, account, Decimal("100.00"))
        _allocate(brazos, payment, invoice, Decimal("100.00"))

        monkeypatch.setattr(payments_seam, "allocated_against_invoice", lambda _id: None)
        assert _impact(invoice).settlement is None


def test_cs36_task20_tc8__the_preview_carries_it_in_section_SIX(brazos, dana):
    """BR-BIL-044's NINE sections stay nine — this rides inside the balance one.

    *"Nine sections, all required, none collapsible away"* is a ratified
    contract, so the settlement is NOT a tenth section. It sits in
    `the_customers_balance`, beside the `reallocation_plan` SENTENCE that
    promised this behaviour and that nobody executed until 2026-09-01.
    """
    from apps.billing import single_correction

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0148")
        invoice.total = Decimal("100.00")
        invoice.save(update_fields=["total"])
        payment = _a_cleared_payment(brazos, account, Decimal("100.00"))
        _allocate(brazos, payment, invoice, Decimal("100.00"))

        impact = _impact(invoice, corrected_total=Decimal("80.00"))
        assert impact.as_dict()["settlement"]["still_owed"] == "0.00"
        # The section names are the ratified contract and they do not move.
        assert len(single_correction.PREVIEW_SECTIONS) == 9
        assert "settlement" not in [name for _, name in single_correction.PREVIEW_SECTIONS]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-36 · §10 (S30's settlement panel) · §11 task 20 ·
#         04-docs/05-modules/06-billing/02-business-rules.md BR-BIL-044/072 ·
#         04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-010/041/1072
# generated: 2026-09-02 by the CR-059 task 20 lane (CS-36's screens)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 row in
#         12-governance/09-human-review-ledger.md, `corrections.py` is guarded)
# gates: RED PROVED FIRST — every case failed on `AttributeError: 'BillImpact'
#         object has no attribute 'settlement'` before the service existed, and
#         TC-5 failed `assert '20.00' == '0.00'` against a draft that let a
#         NEGATIVE credit position buy the replacement bill
# exceptions: (1) SQLite is enough for these eight. They are pure arithmetic
#         over rows this file writes itself and there is no catch-and-continue
#         anywhere on the path, so hard-won law 14's PostgreSQL requirement does
#         not bind here — the RELEASE that these figures describe IS proved on
#         PostgreSQL, in `test_cr059_cs36_restatement_pg.py`, which is task 21.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
