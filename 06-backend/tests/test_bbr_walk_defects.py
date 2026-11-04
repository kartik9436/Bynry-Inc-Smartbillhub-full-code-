# ── Trace ──────────────────────────────────────────────
# Journey:  J72 (the bulk bill run walked on PostgreSQL, 2026-09-30) — the walk
#           found these; each test is the walk's own account shape.
# Defects:  DEF-BIL-8473 (an overlap covering the whole period, unanswered,
#           was drafted a second base) · DEF-BIL-8474 (paid after cut-off,
#           unanswered: no bill, no break, no Pending row, Sign off counted it
#           billed) · DEF-BIL-8472 (an overlap row offered "Bill as it stands")
# Rules:    PO 2026-09-30 fixed-charge case 4 (`16-check-decisions-next-bill.md`
#           §2: "Bill as is" removed for overlaps; a last bill covering the
#           WHOLE period is put to the clerk with Hold only) · BR-BIL-1054
#           (every account not billed enters Pending billing at Send)
# ───────────────────────────────────────────────────────
"""The walk's three Check/Calculate defects, written red first against
`8040f184d` + the bulk-run-rest lane (2.413.0)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import check_store, decisions, pending, runs, selectors, signoff
from apps.billing import models as billing_models

from tests.test_bbr_fixed_charge_next_bill import AUGUST, SEPTEMBER, _run, _setup
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db


def _issued(brazos, account, run, window, total="8", **extra):
    """An issued bill covering `window` — the walk's sent one-time bill. Every
    field is set at creation: an issued invoice is frozen (hard rule 4, the
    `billing_invoice_immutable` trigger on PostgreSQL)."""
    return billing_models.Invoice.objects.create(
        **extra,
        tenant=brazos,
        account=account,
        bill_run=run,
        service_date=window[1],
        period_start=window[0],
        period_end=window[1],
        status=billing_models.INVOICE_ISSUED,
        currency="USD",
        subtotal=Decimal(total),
        tax_total=Decimal("0"),
        total=Decimal(total),
    )


def _whole_period_overlap(brazos, dana, account_no, asset_no):
    cycle, account, asset = _setup(brazos, dana, account_no=account_no, asset_no=asset_no, base="8")
    earlier = runs.create_run(
        cycle_id=cycle.id,
        period_start=AUGUST[0],
        period_end=AUGUST[1],
        bill_date=date(2026, 9, 1),
        label="August",
    )
    _issued(brazos, account, earlier, SEPTEMBER)  # Sep 1 – Sep 30, already sent
    commit_read(
        dana,
        asset.id,
        day="2026-09-28",
        value="1000",
        prior_value="990",
        consumption="10.000000",
        unit="kWh",
    )
    september, _bare = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
    # The calculate job's own prepare (`run_jobs`: `selectors.prepared_for`),
    # with the run's payment window — the path the walk took.
    return cycle, account, september, selectors.prepared_for(september)


# BULK-CHG-51
def test_8473__an_overlap_covering_the_whole_period_with_no_answer_is_not_priced(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, account, september, prepared = _whole_period_overlap(
            brazos, dana, "A-08473", "M-8473"
        )
        raised = [p.reason for p in prepared.decisions if p.account_id == str(account.id)]
        applied = decisions.apply_decisions(prepared, bill_run=september)
        runs.calculate_run(applied, bill_run=september)
        drafted = billing_models.Invoice.objects.filter(account=account, bill_run=september)
        print(f"\nPROOF 8473: raised {raised}; drafted {drafted.count()} (Sep already billed $8.00)")
        assert "billing_continuity" in raised
        assert str(account.id) not in {d.account_id for d in applied.ready}
        assert not drafted.exists(), "the same days' $8.00 base would be billed twice"


# BULK-CHG-51
def test_8473__a_standing_bill_as_is_never_bills_an_overlap(brazos, dana):
    """*Answer for all* on the Gap-or-overlap tag says Bill as it stands; an
    overlap row is still not billed as is (PO: removed for overlaps)."""
    with tenant_ctx(brazos):
        _cycle, account, september, prepared = _whole_period_overlap(
            brazos, dana, "A-08476", "M-8476"
        )
        decisions.set_standing_answer(
            bill_run=september, case="billing_continuity", choice="bill_as_is"
        )
        applied = decisions.apply_decisions(prepared, bill_run=september)
        runs.calculate_run(applied, bill_run=september)
        assert not billing_models.Invoice.objects.filter(
            account=account, bill_run=september
        ).exists()


# BULK-CHG-51 · BULK-CHG-36 (DEF-BIL-8472, the server half)
def test_8472__each_continuity_row_serves_its_own_answers(brazos, dana):
    """A gap row offers Bill as it stands and Investigate; an overlap row
    offers Investigate only — served PER ROW, so the screen never offers an
    answer the server refuses."""
    with tenant_ctx(brazos):
        _cycle, account, september, _prepared = _whole_period_overlap(
            brazos, dana, "A-08472", "M-8472"
        )
        check_store.check_run(september)
        page = check_store.tag_accounts(september, "billing_continuity", {})
        found = check_store.account_findings(september, str(account.id))
    [row] = [r for r in page["results"] if r["account_id"] == str(account.id)]
    [finding] = [f for f in found["findings"] if f["code"] == "billing_continuity"]
    assert row["choices"] == ["investigate"]
    assert finding["choices"] == ["investigate"]
    assert "bill_as_is" in page["tag"]["choices"], "the TAG still offers both (a gap row may take it)"


# BULK-CHG-38 · BULK-CHG-36 — DEF-BIL-8471
def test_8471__paid_after_cutoff_is_served_under_payments_and_balances_with_its_own_name():
    """The walk saw *Other decision* under Setup because the screen grouped on
    a client map that gave the tag no codes. The screen now reads the SERVER's
    grouping (DEF-BIL-8216), so the tag is where the taxonomy puts it, named by
    its own catalogue key."""
    import json
    import pathlib

    from apps.billing import check_taxonomy

    tag = check_taxonomy.classify("paid_after_cutoff")
    payload = {c["category"]: c for c in check_taxonomy.categories_payload()}
    en = json.loads(
        (pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json").read_text()
    )
    assert tag.category == check_taxonomy.CAT_PAYMENTS and tag.severity == "decision"
    assert "paid_after_cutoff" in [t["code"] for t in payload[check_taxonomy.CAT_PAYMENTS]["tags"]]
    assert en[tag.label_key] == "Paid after cut-off"


# BULK-CHG-38 · BULK-CHG-40 · BULK-CHG-37
def test_8474__paid_after_cutoff_unanswered_is_not_billed_is_queued_and_not_counted_billed(
    brazos, dana
):
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        cycle, account, asset = _setup(brazos, dana, account_no="A-08474", asset_no="M-8474", base="8")
        august = runs.create_run(
            cycle_id=cycle.id,
            period_start=AUGUST[0],
            period_end=AUGUST[1],
            bill_date=date(2026, 9, 1),
            label="August",
        )
        august_bill = _issued(
            brazos,
            account,
            august,
            AUGUST,
            total="200",
            invoice_no="BL-2609-008474",
            issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
            due_date=date(2026, 9, 22),
        )
        payment = payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("120.000000"),
            currency="USD",
            status=payment_models.PAYMENT_CLEARED,
            posted_at=datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc),
        )
        payment_models.Allocation.objects.create(
            tenant=brazos, payment=payment, invoice=august_bill, amount=Decimal("120")
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
        september, _bare = _run(cycle, SEPTEMBER, date(2026, 10, 1), "September")
        prepared = selectors.prepared_for(september)
        check_store.check_run(september)
        status = check_store.account_statuses(september)[str(account.id)]
        runs.calculate_run(decisions.apply_decisions(prepared, bill_run=september), bill_run=september)
        drafted = billing_models.Invoice.objects.filter(account=account, bill_run=september).exists()
        summary = signoff.sign_off_summary(september)
        written = pending.queue_not_in_run(bill_run=september)
        row = billing_models.BillRunExclusion.objects.filter(
            bill_run=september, account=account
        ).first()
    who = summary["who_is_billed"]["accounts"]
    print(
        f"\nPROOF 8474: status {status}; drafted {drafted}; billed {who['billed']}, held {who['held']}; "
        f"queued {row.reason_code if row else None}"
    )
    assert status == "decision"
    assert not drafted, "never billed on an answer nobody gave"
    assert who["billed"] == 0 and who["held"] == 1, "Sign off never counts it billed"
    assert who["reconciles"] is True
    assert written == 1 and row is not None and row.reason_code == pending.REASON_CHECK_UNDECIDED
