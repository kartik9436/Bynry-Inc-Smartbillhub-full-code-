# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 §8 CS-36, task 14 — "CS-36's cheap half: raise
#           `bill_already_paid_in_full` on its own, ahead of the fix"
#           Screens: S30 (the Fix-a-bill preview renders the warning list)
# Rules:    BR-PAY-1072 (a restatement of a bill that is already paid WARNS
#           before it is approved) · BR-BIL-072 (what a bill ASKS for is its
#           level, not its total — PO 2026-08-11 "Level is due") · BR-BIL-044
#           (the preview is the approval artifact) · BR-BIL-046 (the aggregate
#           counts warned rows) · B1 (no cross-module import; the allocation
#           figure is asked for by name)
# Tests:    this file
# Impacts:  apps/billing/corrections.py (`_paid_in_full_warning`) ·
#           apps/billing/payments_seam.py (`allocated_against_invoice`)
# ───────────────────────────────────────────────────────
"""The warning the constant declared and no code path ever appended.

════════════════════════════════════════════════════════════════════════════
WHAT WAS ACTUALLY WRONG, AND IT IS ONE LINE OF EVIDENCE
════════════════════════════════════════════════════════════════════════════
`WARN_PAID_IN_FULL = "bill_already_paid_in_full"` has sat at
`apps/billing/corrections.py:202` since the module was written. A repository-
wide grep for the string found it **once** — its own definition. Three sibling
codes on the same six lines are appended to `warnings` in `build_impact`; this
one never was, so a clerk about to restate a bill the customer has already
settled in full was told about upward corrections and closed posting periods
and nothing whatever about the payment.

CS-36's ⚠ note asks for exactly this, ahead of the money fix, and says why:
*"It will not fix anything, but it puts the fact in front of the clerk who is
about to correct a paid bill, which is the person best placed to notice that
the number afterwards is wrong."*

════════════════════════════════════════════════════════════════════════════
WHAT RUNS HERE — stated, because it changes what these tests are worth
════════════════════════════════════════════════════════════════════════════
Real rows on both sides of the seam: billing's issued invoice and its lines,
payments' `allocations` written against it. **The seam is NOT stubbed** — the
warning is produced by `build_impact` resolving `apps.payments.billing_seam.
allocated_so_far` by name, which is the wiring hard-won law 2 is about. The
one case that stubs anything stubs the seam to be ABSENT, which is the point
of that case.

NOTHING HERE EXECUTES A CORRECTION. Task 14 is the preview half; the release
that makes the money right is task 19 and is proved separately, on PostgreSQL.
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

#: WE-9's issued bill, imported rather than retyped — 247.87.
ORIGINAL_TOTAL = Decimal("247.87")
POSTED_AT = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)


def _a_cleared_payment(tenant, account, amount: Decimal, *, no: str = "PMT-000001"):
    """One cleared receipt on the account. No allocation of its own yet."""
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
        lines=(
            _RatedLine("usage", "Water usage 6 kgal", total - Decimal("60.00")),
            _RatedLine("base", "Water base charge", Decimal("39.03")),
            _RatedLine("tax", "TX State 6.25%", Decimal("20.97")),
        ),
    )


def _warning_codes(impact) -> list[str]:
    return [warning["code"] for warning in impact.warnings]


def _impact(invoice, *, correction_class=CLASS_RESTATEMENT, corrected_total=Decimal("227.95")):
    return corrections.build_impact(
        invoice,
        reason_codes=("meter_read_error",),
        correction_class=correction_class,
        corrected=(
            _corrected_bill(corrected_total) if correction_class == CLASS_RESTATEMENT else None
        ),
        goodwill_amount=Decimal("25.00") if correction_class == CLASS_CREDIT_ONLY else None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · the case CS-36 is written from
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task14_tc1__a_fully_paid_bill_warns_with_both_figures(brazos, dana):
    """A restatement of a bill the customer has settled says so, and quotes it.

    CS-36's Ajinkya: a bill paid in full on time, corrected three weeks later.
    Both figures appear because a warning that says "already paid" without
    saying *how much* leaves the clerk to go and find out, which is the thing
    that does not happen.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0141")
        payment = _a_cleared_payment(brazos, account, ORIGINAL_TOTAL)
        _allocate(brazos, payment, invoice, ORIGINAL_TOTAL)

        impact = _impact(invoice)

        assert corrections.WARN_PAID_IN_FULL in _warning_codes(impact)
        warning = next(w for w in impact.warnings if w["code"] == corrections.WARN_PAID_IN_FULL)
        assert "247.87 USD has been applied" in warning["detail"]
        assert "247.87 USD it asks for" in warning["detail"]
        # The structured field carries the ids; the sentence a clerk reads
        # carries none (B14 rules 31/32, ratified 2026-08-31).
        assert "BR-" not in warning["detail"]
        assert "OQ-" not in warning["detail"]


def test_cs36_task14_tc2__an_overpaid_bill_warns_too(brazos, dana):
    """Paid MORE than it asked for is still paid in full.

    `>=`, never `==`: a customer who paid 250.00 against a 247.87 bill has
    settled it, and a warning that fired only on the exact cent would go silent
    on the case where MORE of the customer's money is pointing at a bill that
    is about to be replaced.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0142")
        payment = _a_cleared_payment(brazos, account, Decimal("250.00"))
        _allocate(brazos, payment, invoice, Decimal("250.00"))

        assert corrections.WARN_PAID_IN_FULL in _warning_codes(_impact(invoice))


def test_cs36_task14_tc3__a_part_paid_bill_does_not_warn(brazos, dana):
    """60.00 against 247.87 is not "paid in full", and the code says so.

    The constant names a fact. A warning that fired on any payment at all would
    be a different warning wearing this one's name, and CS-36's partly-paid
    shape (60.00 of 100.00) is a lawful, ordinary correction.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0143")
        payment = _a_cleared_payment(brazos, account, Decimal("60.00"))
        _allocate(brazos, payment, invoice, Decimal("60.00"))

        assert corrections.WARN_PAID_IN_FULL not in _warning_codes(_impact(invoice))


def test_cs36_task14_tc4__an_unpaid_bill_does_not_warn(brazos, dana):
    """The ordinary correction, unchanged. Nothing new appears on it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0144")

        assert corrections.WARN_PAID_IN_FULL not in _warning_codes(_impact(invoice))


def test_cs36_task14_tc5__a_bill_re_opened_by_a_bounce_does_not_warn(brazos, dana):
    """The cheque bounced, so the bill is open again — and the warning knows.

    The reversing rows are NEGATIVE allocations hung off the reversing payment
    (BR-PAY-031), so the seam's NET sum is 0.00 and this bill is unpaid. A read
    that summed only positive rows would warn about a payment that came back.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0145")
        original = _a_cleared_payment(brazos, account, ORIGINAL_TOTAL)
        _allocate(brazos, original, invoice, ORIGINAL_TOTAL)
        bounce = payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-000002",
            amount=-ORIGINAL_TOTAL,
            currency="USD",
            status=payment_models.PAYMENT_REVERSED,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            reverses_payment=original,
        )
        _allocate(brazos, bounce, invoice, -ORIGINAL_TOTAL)

        assert corrections.WARN_PAID_IN_FULL not in _warning_codes(_impact(invoice))


def test_cs36_task14_tc6__a_budget_bill_paid_at_its_level_warns(brazos, dana):
    """❄️ WE-8 — a 292.87 bill that ASKS for 242.00, paid at 242.00.

    BR-BIL-072 (PO 2026-08-11, *"Level is due"*): what a budget-billing bill
    asks for is its LEVEL. Measuring "paid in full" at `invoice.total` instead
    would call this customer 50.87 short — DEF-2416 re-opened in a new place,
    and a SECOND definition of "settled", which is the shape of the defect
    CS-36 is itself made of.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-0146",
            total=Decimal("292.87"),
            bill_payload={
                "account_no": account.account_no,
                "customer_name": "Sara Whitfield",
                "budget": {"amount_due": "242.00"},
            },
        )
        payment = _a_cleared_payment(brazos, account, Decimal("242.00"))
        _allocate(brazos, payment, invoice, Decimal("242.00"))

        impact = _impact(invoice, corrected_total=Decimal("272.95"))
        warning = next(w for w in impact.warnings if w["code"] == corrections.WARN_PAID_IN_FULL)
        assert "242.00 USD has been applied" in warning["detail"]
        assert "242.00 USD it asks for" in warning["detail"]


def test_cs36_task14_tc7__a_goodwill_credit_on_a_paid_bill_does_not_warn(brazos, dana):
    """Class C leaves the bill alone, so a payment against it goes nowhere wrong.

    PO 2026-08-11: *"you dont touch the bill; you issue new a good will
    credit"*. Nothing is being replaced, so nothing is about to point at a
    replaced bill, so there is nothing to warn about.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0147")
        payment = _a_cleared_payment(brazos, account, ORIGINAL_TOTAL)
        _allocate(brazos, payment, invoice, ORIGINAL_TOTAL)

        impact = _impact(invoice, correction_class=CLASS_CREDIT_ONLY)
        assert corrections.WARN_PAID_IN_FULL not in _warning_codes(impact)


def test_cs36_task14_tc8__a_document_correction_on_a_paid_bill_does_not_warn(brazos, dana):
    """Class D moves $0.00 (BR-BIL-043), so no payment is disturbed."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0148")
        payment = _a_cleared_payment(brazos, account, ORIGINAL_TOTAL)
        _allocate(brazos, payment, invoice, ORIGINAL_TOTAL)

        impact = _impact(invoice, correction_class=CLASS_DOCUMENT)
        assert corrections.WARN_PAID_IN_FULL not in _warning_codes(impact)


def test_cs36_task14_tc9__an_unreachable_seam_warns_nothing_rather_than_the_opposite(
    brazos, dana, monkeypatch
):
    """`None` is not `0.00`, and the difference here is a lie about a payment.

    A deployment whose payments module is not published cannot be told whether
    this bill was paid. It must not therefore be told that it was NOT — the
    seam's own rule (`deposit_paid_for_account`'s $150.00 lesson) applied to a
    warning instead of to a charge.
    """
    from apps.billing import payments_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0149")
        payment = _a_cleared_payment(brazos, account, ORIGINAL_TOTAL)
        _allocate(brazos, payment, invoice, ORIGINAL_TOTAL)

        assert corrections.WARN_PAID_IN_FULL in _warning_codes(_impact(invoice))

        monkeypatch.setattr(payments_seam, "_resolve", lambda module, attribute: None)
        assert payments_seam.allocated_against_invoice(invoice.pk) is None
        assert corrections.WARN_PAID_IN_FULL not in _warning_codes(_impact(invoice))


def test_cs36_task14_tc10__the_warning_joins_the_others_rather_than_replacing_them(brazos, dana):
    """An upward correction on a paid bill carries BOTH warnings.

    BR-BIL-046 groups the S30 preview on these codes and counts warned rows, so
    a list that dropped a sibling would change what an approver is shown about
    the back-bill cap.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        invoice = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0150")
        payment = _a_cleared_payment(brazos, account, ORIGINAL_TOTAL)
        _allocate(brazos, payment, invoice, ORIGINAL_TOTAL)

        codes = _warning_codes(_impact(invoice, corrected_total=Decimal("267.87")))
        assert corrections.WARN_UPWARD in codes
        assert corrections.WARN_PAID_IN_FULL in codes


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-36 (the specification) · §11 task 14 · §7 (how payments
#         works today — `allocated_so_far`, the NET sum) · CLAUDE.md rules 1/2
# generated: 2026-09-01 by the CR-059 W4 CS-36 lane (tasks 14/19/21)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the warning rides on the existing
#         S30 preview payload; no route changed) E=deferred(no-frontend-half —
#         the settlement panel that renders it is task 20, NOT this task) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED first — see the lane report for the verbatim
#         transcript at the pinned tip, where TC-1 fails
#         `assert 'bill_already_paid_in_full' in ['correction_increases_...']`
# exceptions: (1) the correction is PREVIEWED and never EXECUTED here; task 19's
#         release and task 21's PostgreSQL proof are separate files.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
