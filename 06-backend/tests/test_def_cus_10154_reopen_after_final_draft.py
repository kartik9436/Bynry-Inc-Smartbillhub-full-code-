# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10154 — a reopened account (CR-181) kept its move-out's
#           final DRAFT and the next cycle run billed the same days again
#           (combined walk 2026-10-14: Viktor Valdez AC-2026-00022, draft
#           10/01–10/12 $205.38 + October bill 10/01–10/31 $292.15).
# Rules:    Coordinator decision 2026-10-14 (decision log *"A REOPENED
#           ACCOUNT'S NEXT BILL STARTS THE DAY AFTER ITS FINAL BILL"*) ·
#           DEF-CUS-10093 (PO 2026-10-13 option B) · BR-BIL-004 · fixed-charge
#           case 4 (PO 2026-09-30) · hard-won law 14 (run on PostgreSQL too)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A reopened account's next bill starts the day after its final bill.**

Re-cast on this suite's fixtures: a metered account opened 1 June, read
13,800 → 14,100 on the move day, 12 June (300 kWh). The move-out's Complete
drafts the final bill 1–12 June. The customer comes back and the SAME account
is reopened on 14 June; the meter reads 14,400 on 30 June. The June cycle run
must bill **13–30 June, 300 kWh** — never 1–30 June, 600 kWh, which bills
1–12 June a second time on top of the final draft.

  * the final bill still a DRAFT          → 13–30 June, 300 kWh;
  * the final bill SENT (issued)          → 13–30 June, 300 kWh (the same);
  * the final draft CANCELLED (discarded) → 1–30 June, the cycle's own start:
    nothing billed 1–12 June any more, so nothing to start after.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting the
period alone — a shortened period still measured from the 31 May reading
would bill 600 kWh over 18 days — so every case asserts the QUANTITY too; and
a draft case that passed because no draft existed (each asserts the draft's
status and window first).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import runs, selectors
from apps.billing import final_bill
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from tests.test_br_bil_013_final_bill_preview import _a_moving_out_account
from tests.test_us_bil_011_final_bill import MOVE_OUT
from tests.test_us_bil_001_prepare import PERIOD_END, PERIOD_START
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db

REOPENED_ON = date(2026, 6, 14)
DAY_AFTER_FINAL = date(2026, 6, 13)


@pytest.fixture(autouse=True)
def _days_to_pay(monkeypatch):
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "06-S", "name": "Cycle 06", "due_days": 21},
    )


def _moved_out_and_reopened(brazos, dana, monkeypatch, *, asset_no, account_no):
    """Move out on 12 June (Complete drafts the final bill), reopen on the 14th,
    read 14,400 on the 30th. Returns `(account, final draft, meter id)`."""
    from apps.assets import models as asset_models

    account = _a_moving_out_account(
        brazos, dana, monkeypatch, asset_no=asset_no, account_no=account_no
    )
    open_status_id = account.status_id
    result = customer_services.move_out(dana, account.id, {"moved_out_on": MOVE_OUT.isoformat()})
    assert result["final_bill"]["outcome"] == "drafted", result["final_bill"]
    (final,) = billing_models.Invoice.objects.filter(account_id=account.id, bill_type="final")
    assert final.status == billing_models.INVOICE_DRAFT
    assert (final.period_start, final.period_end) == (PERIOD_START, MOVE_OUT)
    # CR-181's reopen, as its own writes leave the row: the SAME account active
    # again from the move-in day, `closed_at` cleared. The final draft is not
    # touched by the reopen — that is the defect's starting state.
    customer_models.Account.objects.filter(pk=account.pk).update(
        status_id=open_status_id, closed_at=None, opened_at=REOPENED_ON
    )
    meter = asset_models.Asset.objects.get(tenant=brazos, asset_no=asset_no)
    commit_read(
        dana,
        meter.id,
        day=PERIOD_END.isoformat(),
        value="14400",
        prior_value="14100",
        consumption="300.000000",
        unit="kWh",
    )
    return customer_models.Account.objects.get(pk=account.pk), final


def _june_run(account):
    unit_cycle = _cycle_of(account)
    prepared = runs.prepare_run(
        cycle_id=unit_cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=PERIOD_END,
    )
    (data,) = [d for d in prepared.ready if d.account_no == account.account_no]
    (electric,) = [r for r in data.readings if r.service_code == "electric"]
    return data, electric


def _cycle_of(account):
    from apps.metering import models as metering_models

    point = metering_models.ServicePoint.objects.filter(unit_id=account.unit_id).first()
    return point.cycle_id


def test_draft_final_bill_the_next_cycle_bill_starts_the_day_after_it(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account, final = _moved_out_and_reopened(
            brazos, dana, monkeypatch, asset_no="M-9541", account_no="A-15401"
        )
        assert selectors.last_issued_service_period_end(account.id) == MOVE_OUT
        data, electric = _june_run(account)

    assert data.period_start == DAY_AFTER_FINAL, data.period_start
    assert data.period_end == PERIOD_END
    # Measured from the final bill's 12 June reading, never from before it.
    assert electric.consumption.amount == Decimal("300"), electric.consumption
    # The final draft stays a valid bill for the earlier tenancy, untouched.
    final.refresh_from_db()
    assert final.status == billing_models.INVOICE_DRAFT
    assert final_bill.move_out_final_draft(final) is True


def test_sent_final_bill_the_next_cycle_bill_starts_the_day_after_it(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account, final = _moved_out_and_reopened(
            brazos, dana, monkeypatch, asset_no="M-9542", account_no="A-15402"
        )
        billing_models.Invoice.objects.filter(pk=final.pk).update(
            status=billing_models.INVOICE_ISSUED
        )
        data, electric = _june_run(account)

    assert data.period_start == DAY_AFTER_FINAL
    assert electric.consumption.amount == Decimal("300"), electric.consumption


def test_cancelled_final_draft_the_next_bill_starts_on_the_cycle(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        account, final = _moved_out_and_reopened(
            brazos, dana, monkeypatch, asset_no="M-9543", account_no="A-15403"
        )
        run = billing_models.BillRun.objects.get(pk=final.bill_run_id)
        runs.discard_run(run, actor=dana)
        assert not billing_models.Invoice.objects.filter(pk=final.pk).exists()
        assert selectors.last_issued_service_period_end(account.id) is None
        data, electric = _june_run(account)

    # Nothing covers 1–12 June now, so the cycle's own start and every day's usage.
    assert data.period_start == PERIOD_START
    assert electric.consumption.amount == Decimal("600"), electric.consumption


def test_only_a_move_out_final_draft_anchors(brazos, dana, monkeypatch):
    """A final draft WITHOUT the move-out marker (the One-time tab's) and a cycle
    run's draft are not an account's billed position — `billed_position_q`."""
    with tenant_ctx(brazos):
        account, final = _moved_out_and_reopened(
            brazos, dana, monkeypatch, asset_no="M-9544", account_no="A-15404"
        )
        payload = dict(final.bill_payload or {})
        payload.pop(final_bill.MOVE_OUT_DRAFT_MARKER)
        billing_models.Invoice.objects.filter(pk=final.pk).update(bill_payload=payload)
        assert selectors.last_issued_service_period_end(account.id) is None
        assert runs.last_issued_window(account.id) is None
    # The marker billing reads is the one the move-out writes.
    assert selectors.MOVE_OUT_DRAFT_MARKER == final_bill.MOVE_OUT_DRAFT_MARKER
