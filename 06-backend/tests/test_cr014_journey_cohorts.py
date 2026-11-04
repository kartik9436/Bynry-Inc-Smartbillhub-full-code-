# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 — every journey must have a working fixture. These are the
#           declared cases for the SHARED flat money cohort the W11 lane built
#           (tests/journey_cohort_fixtures.py), written BEFORE the seeder was
#           trusted (r11 step 2c/2d).
# Rules:    money-triples row `flat,cycle,full` (89.00 + 8.41 = 97.41, frozen
#           B4 math via 10-scripts/04-e2e-expected-gen.py) · US-BIL-008 §4 (the
#           four-authority set, four lines never one 9.45%) · BR-BIL-024 (due =
#           bill date + due-days) · OQ-218 CLOSED 2026-08-16 ("no reason to
#           disturb a signed figure") — the cohort must leave the signed July
#           window EXACTLY as LE-1 posted it · CLAUDE.md rule 6 (idempotent).
# Red-proof: tc1 shown RED with the tier price at 0.12 (total 104.98 ≠ 97.41);
#           tc3 shown RED with the run's service date moved to Jul 31 (July
#           window 651.10 ≠ 553.69). Both quoted in the W11 lane report,
#           2026-08-22.
# ───────────────────────────────────────────────────────
"""CR-014 — the flat journey cohort prices the dataset row, and nothing else.

The danger CR-014 names is not that a journey fails — it is that a journey
over an empty or wrong cohort PASSES. So the cohort builder refuses to report
success unless the issued bill IS the dataset row, and these tests hold that
refusal to its word — including the one property no journey would ever catch:
that building the cohort does not restate the finance-signed July book.
"""

from decimal import Decimal

import pytest

from tests import journey_cohort_fixtures as cohort
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_cr014_tc1__the_flat_cohort_prices_the_dataset_row(brazos, dana):
    """money-triples `flat,cycle,full`: 700 kWh × 0.11 + 12.00 base = 89.00
    taxable · four authority lines 5.56 + 0.89 + 1.78 + 0.18 = 8.41 · total
    97.41 · due = bill date Sep 1 + 21 due-days = Sep 22."""
    with tenant_ctx(brazos):
        result = cohort.ensure_flat_cohort(brazos, dana)

    assert result["total"] == "97.41"
    assert sorted(result["tax_lines"]) == ["0.18", "0.89", "1.78", "5.56"]
    assert result["due_date"] == "2026-09-22"


def test_cr014_tc2__seeding_twice_mints_nothing_twice(brazos, dana):
    """CLAUDE.md rule 6 — a re-booted stack re-runs every seeder; the second
    pass must find the world and write no second cohort."""
    from apps.billing import models as billing_models
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        cohort.ensure_flat_cohort(brazos, dana)
        cohort.ensure_flat_cohort(brazos, dana)

        issued = billing_models.Invoice.objects.filter(
            tenant=brazos,
            status="issued",
            account__account_no=cohort.ACCOUNT_PRIMARY,
        ).count()
        accounts = customer_models.Account.objects.filter(
            tenant=brazos, account_no=cohort.ACCOUNT_PRIMARY
        ).count()

    assert issued == 1
    assert accounts == 1


def test_cr014_tc3__the_signed_july_window_is_untouched(brazos, dana):
    """OQ-218's ruling, held as an invariant: LE-1's July window foots at
    553.69 BEFORE the cohort is built and at 553.69 AFTER, row for row.

    This is the reason the cohort bills August: an issued bill posts its
    journal entry at the bill's service date, so any July-period bill would
    move this exact figure. A journey suite could go green forever without
    noticing — only this comparison sees it.
    """
    from apps.ledger import reporting
    from tests import ledger_le_fixtures as le

    with tenant_ctx(brazos):
        world: dict = {}
        accounts = le.make_accounts(dana, brazos, world, service="electric")
        le.post_le1_month(brazos, accounts)

        before = reporting.trial_balance(start=le.JULY_START, end=le.JULY_END)
        cohort.ensure_flat_cohort(brazos, dana)
        after = reporting.trial_balance(start=le.JULY_START, end=le.JULY_END)

    assert before["total_debit"] == after["total_debit"]
    assert before["total_credit"] == after["total_credit"]
    assert before["rows"] == after["rows"]
    # And the figure itself is the signed one, so a drifted LE fixture goes
    # red here rather than silently anchoring the comparison somewhere new.
    assert Decimal(str(after["total_debit"])) == Decimal("553.69")


def test_cr014_tc4__oq219_reconciliation_moves_the_cash(brazos, dana):
    """OQ-219 CLOSED 2026-08-16 — PO: the fixture month's payment is
    RECONCILED, so the month renders realised cash 442.87 / undeposited 0.00
    (not 150.00 / 292.87), with the trial balance unmoved at 598.69 = 598.69.

    `seed_journey_fixture.seed_j19` now calls `le.reconcile_the_payment`; this
    asserts the arithmetic that call is trusted for.
    """
    from apps.ledger import reporting
    from tests import ledger_le_fixtures as le

    with tenant_ctx(brazos):
        world: dict = {}
        accounts = le.make_accounts(dana, brazos, world, service="electric")
        le.post_le1_month(brazos, accounts)
        le.reconcile_the_payment(brazos, accounts)

        whole = reporting.trial_balance(start=le.CUTOVER, end=None)
        balances = {row["code"]: row for row in whole["rows"]}

    # Both states foot — which is why OQ-219 was a choice, not an error — so
    # the totals hold AND the cash moved.
    assert Decimal(str(whole["total_debit"])) == Decimal(str(whole["total_credit"]))
    cash = Decimal(str(balances["1000"]["debit"])) - Decimal(str(balances["1000"]["credit"]))
    undeposited = Decimal(str(balances["1010"]["debit"])) - Decimal(
        str(balances["1010"]["credit"])
    )
    assert cash == le.LE1_CASH_TOTAL  # 442.87
    assert undeposited == Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-014 · W11 lane 2026-08-22
# generated: 2026-08-22
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: pytest (this file) · golden 33/33 unchanged
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
