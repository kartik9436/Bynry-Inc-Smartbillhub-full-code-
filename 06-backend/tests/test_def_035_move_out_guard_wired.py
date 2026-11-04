# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (move-out) · US-BIL-005 (the issued bill it protects)
#           Screens: S20
# Rules:    BR-BIL-004 (issued bills are immutable; corrections are new rows) ·
#           BR-CUS-030 (move-out dating) · CLAUDE.md rule 4
# ───────────────────────────────────────────────────────
"""DEF-035 — the move-out guard was written, tested, and had never run.

`_check_move_out_against_issued_bills` has refused a move-out dated behind the
last issued bill since before `invoices` existed. Its seam resolved
`apps.billing.SERVICES.last_issued_invoice_period_end`; billing's services
module publishes only `assess_late_fee`. So the lookup returned None on every
call, the guard recorded "could not check", and the move-out went through.

Its own tests passed the whole time, because they monkeypatch the seam — which
is exactly what made this invisible. A test that supplies the answer cannot
discover that nobody was asking the question.

So this file does the one thing those tests could not: it drives the REAL seam
against a REAL issued bill. If the wiring breaks again, this goes red.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.customers import seams as customer_seams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def test_def_035_tc1__the_seam_reaches_a_real_issued_bill(brazos, dana):
    """THE ONE ASSERTION THAT WAS MISSING: the seam resolves and answers.

    Not "the guard refuses when told a date" — that was always covered. This
    is "the guard can find out", which is what had never been true.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="1408 Bluestem Ln")
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])
        account = customer_models.Account.objects.create(
            tenant=brazos,
            unit_id=unit["id"],
            account_no="A-DEF035",
            status=customer_models.AccountStatus.objects.get(tenant=brazos, code="active"),
            account_type=customer_models.AccountType.objects.first(),
        )

        # No bill yet: the honest answer is None, and it means "nothing billed"
        # rather than "could not ask" — which is why the caller must keep
        # recording the not-checked outcome separately.
        assert customer_seams.last_issued_invoice_period_end(account.id) is None

        billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            invoice_no="BL-2606-000001",
            bill_type="cycle",
            service_date=date(2026, 6, 30),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            status=billing_models.INVOICE_ISSUED,
            subtotal=Decimal("67.940000"),
            tax_total=Decimal("0.000000"),
            total=Decimal("67.940000"),
            currency="USD",
            bill_payload={"account_no": "A-DEF035"},
        )

        assert customer_seams.last_issued_invoice_period_end(account.id) == date(2026, 6, 30)


def test_def_035_tc2__a_draft_does_not_constrain_a_move_out(brazos, dana):
    """Only an ISSUED bill binds. A draft is discardable by rule (BR-BIL-023).

    Getting this backwards would be worse than the defect it fixes: a run that
    drafted 500 bills would freeze 500 accounts out of moving out, for bills
    nobody has sent and that may be replaced within the hour.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="1500 Bluestem Ln")
        unit = make_unit(dana, premises["id"], label="Unit B", services=["electric"])
        account = customer_models.Account.objects.create(
            tenant=brazos,
            unit_id=unit["id"],
            account_no="A-DEF035B",
            status=customer_models.AccountStatus.objects.get(tenant=brazos, code="active"),
            account_type=customer_models.AccountType.objects.first(),
        )
        billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            invoice_no="BL-2606-000002",
            bill_type="cycle",
            service_date=date(2026, 6, 30),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            status=billing_models.INVOICE_DRAFT,
            subtotal=Decimal("10.000000"),
            tax_total=Decimal("0.000000"),
            total=Decimal("10.000000"),
            currency="USD",
        )

        assert customer_seams.last_issued_invoice_period_end(account.id) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@808e015 (04-docs/05-modules/07-billing/02-business-rules.md ·
#         04-docs/05-modules/08-customers/02-business-rules.md)
# generated: 2026-08-11 by Eng-Lead (DEF-035 — wiring a guard that never ran)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a seam read) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED by restoring the seam's `kind` to its
#         default: tc1 failed with the seam answering None against a real
#         issued bill (the exact silent-pass the defect describes)
# exceptions: this asserts the SEAM, not the refusal — the refusal in
#         `customers/services._check_move_out_against_issued_bills` was already
#         correct and already tested, and was never the broken half. Stated so
#         the file is not read as re-testing the guard
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
