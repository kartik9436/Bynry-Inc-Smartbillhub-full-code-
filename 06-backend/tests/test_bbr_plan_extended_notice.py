# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-09-30, fixed-charge case 5 — *"extend the plan by one month
#           … the next bill says the plan now ends a month later"*
#           (`07-billing/16-check-decisions-next-bill.md` §2)
# Defect:   DEF-BIL-8248 (the extension was served; no bill said it)
# Plan:     15-bulk-bill-run-build-plan.md B23 · T8 (two-month tests)
# ───────────────────────────────────────────────────────
"""The bill after a skipped instalment says the plan now ends a month later —
written red first (against `c0e8cbbe9` no snapshot carries `payment_plan` and
no document prints it)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.billing import decisions, documents, gather, payments_seam, runs
from apps.billing import models as billing_models

from tests.test_bbr_fixed_charge_next_bill import (
    OCTOBER,
    SEPTEMBER,
    _bill_and_issue,
    _mine,
    _run,
    _setup,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db


def _september_skipped(brazos, dana):
    """$270 on $45 × 6; September's instalment skipped on the September run
    and the plan extended at issue — the case 5 test's own fixture."""
    from apps.billing import check_store
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment

    cycle, account, asset = _setup(brazos, dana, account_no="A-08248", asset_no="M-8248", base="26")
    plan = PaymentPlan.objects.create(
        tenant=brazos,
        account=account,
        total_amount=Decimal("270"),
        installment_count=6,
        status="active",
        proposed_on=date(2026, 8, 1),
        signed_on=date(2026, 8, 2),
    )
    for seq in range(1, 7):
        PaymentPlanInstallment.objects.create(
            tenant=brazos,
            plan=plan,
            seq=seq,
            due_date=date(2026, 7 + seq, 15) if seq <= 5 else date(2027, 1, 15),
            amount=Decimal("45"),
            paid_posted_on=date(2026, 8, 14) if seq == 1 else None,
        )
    commit_read(
        dana,
        asset.id,
        day="2026-09-28",
        value="1000",
        prior_value="990",
        consumption="10.000000",
        unit="kWh",
    )
    september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
    check_store.check_run(september)
    decisions.record_decision(
        bill_run=september,
        account_id=str(account.id),
        case="plan_instalment_due",
        choice="skip",
        reason="hardship",
    )
    bill = _bill_and_issue(brazos, prepared, september, account)
    extended = payments_seam.extend_plans_for_skips(bill_run=september, account_id=str(account.id))
    return cycle, account, asset, bill, extended


# BULK-CHG-52
def test_8248__the_next_bill_says_the_plan_now_ends_a_month_later(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account, asset, september_bill, extended = _september_skipped(brazos, dana)
        commit_read(
            dana,
            asset.id,
            day="2026-10-28",
            value="1010",
            prior_value="1000",
            consumption="10.000000",
            unit="kWh",
        )
        _october, prepared = _run(cycle, OCTOBER, date(2026, 11, 1), "October")
        [data] = _mine(prepared, "A-08248")

    notice = data.snapshot.get("payment_plan")
    fields, absent = documents._footer({"payment_plan": notice})
    printed = {f.label: f.value for f in fields}
    print(f"\nPROOF case 5 next bill: {notice} → {printed.get('Payment plan')}")
    assert extended["ends_on"] == "2027-02-15"
    assert "payment_plan" not in (september_bill.bill_payload or {}), "not on the skipped bill"
    assert notice == {
        "extended_one_month": True,
        "ends_on": "2027-02-15",
        "amount": "45.000000",
        "currency": "USD",
    }
    assert printed["Payment plan"] == "Now ends 2027-02-15."
    assert all(a.field != "Payment plan" for a in absent)


# BULK-CHG-52
def test_8248__a_bill_with_no_skip_before_it_carries_no_notice(brazos, dana):
    with tenant_ctx(brazos):
        cycle, account, asset = _setup(
            brazos, dana, account_no="A-08249", asset_no="M-8249", base="26"
        )
        commit_read(
            dana,
            asset.id,
            day="2026-09-28",
            value="1000",
            prior_value="990",
            consumption="10.000000",
            unit="kWh",
        )
        _september, prepared = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        [data] = _mine(prepared, "A-08249")
    assert "payment_plan" not in data.snapshot
    fields, _absent = documents._footer({})
    assert "Payment plan" not in {f.label for f in fields}


# BULK-CHG-52
@pytest.mark.skipif(connection.vendor != "postgresql", reason="law 14: PostgreSQL only")
def test_8248_pg__a_failed_statement_in_the_notice_read_never_poisons_the_gather(
    brazos, dana, monkeypatch
):
    """The notice read catches and carries on, so it runs in a SAVEPOINT: a
    real statement error inside it (division by zero) leaves the gather able
    to go on querying, and the bill is gathered with no notice."""
    real = gather._plan_extended_answer

    def broken(account, billing_models):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")
        return real(account, billing_models)

    with tenant_ctx(brazos):
        cycle, account, asset, _bill, _extended = _september_skipped(brazos, dana)
        commit_read(
            dana,
            asset.id,
            day="2026-10-28",
            value="1010",
            prior_value="1000",
            consumption="10.000000",
            unit="kWh",
        )
        monkeypatch.setattr(gather, "_plan_extended_answer", broken)
        _october, prepared = _run(cycle, OCTOBER, date(2026, 11, 1), "October")
        [data] = _mine(prepared, "A-08248")
        still = billing_models.Invoice.objects.filter(account=account).count()
    assert "payment_plan" not in data.snapshot
    assert still == 1, "the transaction was still usable after the failed statement"
    assert runs.price_account(data).priced.total > 0
