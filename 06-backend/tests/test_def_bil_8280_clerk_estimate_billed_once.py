# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8280 (high, money-math) — a Check-decision estimate
#           (`decisions._estimated_reading`) wrote no read and named no read on
#           the bill, so the next period's actual was billed from the last
#           ACTUAL read and the estimated usage was billed TWICE.
# Fix:      PO direction 2026-09-30 (`07-billing/16-check-decisions-next-bill.md`)
#           — at ISSUE the clerk's estimate is saved into Meter Reads through
#           metering's own service as an ESTIMATED reading; metering's true-up
#           (BR-MET-029, ❄️ GT-9 arithmetic) subtracts it at the next real read.
# Proof:    red on the base (`July bills 20` where 15 is owed — the first form of
#           this test, quoted in the defect's close); green with the fix; also
#           run on PostgreSQL (`--ds=config.settings.pgtest`).
# ───────────────────────────────────────────────────────
"""The PO's worked case, two months apart:

    Aug 31   read 1,000 (actual)
    September  no read; the clerk estimates 5 → September's bill: 5 (issued)
    Oct 28   read 1,012 → October bills 12 − 5 = **7**   (before the fix: 12)

Two-month total billed = 5 + 7 = 12 = what the meter measured.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import decisions, metering_seam, runs
from apps.billing import models as billing_models

from tests.test_bbr_check_engine import a_cycle
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import (
    accept_warnings,
    commit_read,
    csv_body,
    seed_config,
    stage,
)

pytestmark = pytest.mark.django_db

SEPTEMBER = (date(2026, 9, 1), date(2026, 9, 30))
OCTOBER = (date(2026, 10, 1), date(2026, 10, 31))


def _prepare(cycle, window, bill_date):
    return runs.prepare_run(
        cycle_id=cycle.id, period_start=window[0], period_end=window[1], service_date=bill_date
    )


# BULK-CHG-47
def test_def_bil_8280__a_clerk_estimate_is_billed_once_not_twice(brazos, dana):
    from apps.assets import models as asset_models
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        seed_config()
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8280", label="U", consumption=None
        )
        account = an_account(brazos, unit["id"], "A-08280")
        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset = asset_models.Asset.objects.get(tenant=brazos, service_point=point)
        commit_read(
            dana, asset.id, day="2026-08-31", value="1000", prior_value="990",
            consumption="10.000000", unit="kWh",
        )

        # ── month 1: no September read; the clerk estimates 5; the bill issues ──
        september = runs.create_run(
            cycle_id=cycle.id, period_start=SEPTEMBER[0], period_end=SEPTEMBER[1],
            bill_date=date(2026, 10, 1), label="September",
        )
        prepared = _prepare(cycle, SEPTEMBER, date(2026, 10, 1))
        assert [p.reason for p in prepared.decisions if p.account_no == "A-08280"] == [
            "missing_read"
        ]
        decisions.record_decision(
            bill_run=september, account_id=str(account.id), case="missing_read",
            choice="estimate", amount=Decimal("5.000000"), unit="kWh",
            service_id=tenancy_selectors.service_ids_by_code()["electric"],
        )
        runs.calculate_run(decisions.apply_decisions(prepared, bill_run=september), bill_run=september)
        bill = billing_models.Invoice.objects.get(tenant=brazos, account=account, bill_run=september)
        [service] = bill.bill_payload["services"]
        assert service["estimated"] is True and service["read_id"] is None
        assert service["estimate"] == {"amount": "5.000000", "unit": "kWh"}
        billing_models.Invoice.objects.filter(pk=bill.pk).update(
            status=billing_models.INVOICE_ISSUED
        )
        bill.refresh_from_db()
        # The issue step's own call (`issue.issue_invoice` → this seam).
        saved = metering_seam.record_billed_estimates(bill)
        assert (saved.recorded, saved.problems) == (1, ())
        again = metering_seam.record_billed_estimates(bill)  # a re-issue records nothing twice
        assert again.recorded == 0 and again.read_ids == saved.read_ids
        estimate_row = metering_models.MeterRead.objects.get(id=saved.read_ids[0])
        assert (estimate_row.status, estimate_row.consumption, estimate_row.lifecycle) == (
            "estimated", Decimal("5.000000"), "billed",
        )

        # ── month 2: the real October read arrives through Meter Reads ───────
        batch = stage(
            dana, csv_body("M-8280,2026-10-28,1012,total,E,"), period_month="2026-10-01"
        )
        metering_services.validate_read_batch(dana, batch["id"])
        accept_warnings(dana, batch["id"])
        metering_services.commit_read_batch(dana, batch["id"], {"certified": True})
        october = _prepare(cycle, OCTOBER, date(2026, 11, 1))

    [data] = [d for d in october.ready if d.account_no == "A-08280"]
    billed = data.readings[0].consumption
    print(
        f"\nPROOF DEF-BIL-8280: September billed 5 kWh (clerk estimate); "
        f"October bills {billed.amount} {billed.unit}; two-month total "
        f"{Decimal('5') + billed.amount} for 12 measured"
    )
    assert billed.unit == "kWh"
    assert billed.amount == Decimal("7"), "the 5 September already billed must not be billed again"


# BULK-CHG-47
def test_def_bil_8280__issue_invoice_saves_the_estimate():
    """The wiring half (hard-won law 2): `issue_invoice` calls the seam."""
    import inspect

    from apps.billing import issue

    source = inspect.getsource(issue.issue_invoice)
    assert "metering_seam.record_billed_estimates(locked" in source
