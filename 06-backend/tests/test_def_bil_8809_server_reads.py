# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8809 (server half) — S2: a cold open of the sent 40,008-bill
#           run's bulk run page shows Not in this run's first row and the Sent
#           card's total in < 2 s
# Journey:  J73 S2 · 08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
# Measured: 04-docs/05-modules/07-billing/19-check-cost-measured.md §15
# Rules:    BR-BIL-056 (the summary recalculates live — PO 2026-08-11, option B)
#           · BR-BIL-064 / OQ-111 / OQ-121 (what these customers owe NOW) ·
#           DEF-BIL-8685 (the Sent card's "Meter reads: Locked") · NFR-3/NFR-5
# ───────────────────────────────────────────────────────
"""The three reads the Send screen waits for, made cheap without moving a figure.

Written red first against `7e49784e4` (2.436.3):

* the run read decoded every sent bill's snapshot and counted its reads in
  Meter Reads (~1.1 s of 1.2 s at 40,008 bills) — the read every screen of the
  page waits for. That fact is now `GET …/read-lock`, asked by the Sent card.
* the page drew two figures of `/summary` (bills, amount) and asked for the
  whole panel (~1.1 s). `GET …/totals` answers the two, with the SAME functions.
* Not in this run decided every account's status twice in Python and then
  skipped every billed one (~0.85 s of 1.0 s). It now reads only the accounts
  the run holds no bill for.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.billing import api as billing_api
from apps.billing import check_store, models, not_in_run, release, selectors
from apps.billing.exceptions import BillingRuleError

from tests.test_bbr_not_in_run import _checked, _priced
from tests.test_us_bil_005_release import a_usage_bill
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

HEADLINE = ("bills", "amount", "currency", "gross_amount", "credits_applied", "credit_count")


def _headline(summary):
    return {
        "bills": summary.bills,
        "amount": summary.amount,
        "currency": summary.currency,
        "gross_amount": summary.gross_amount,
        "credits_applied": summary.credits_applied,
        "credit_count": summary.credit_count,
    }


def _bill(tenant, account, run, total, **overrides):
    # A snapshot on every bill, because PostgreSQL refuses an issued bill
    # without one (BR-BIL-030's trigger) — SQLite would not notice.
    overrides.setdefault("bill_payload", {"services": []})
    return a_usage_bill(
        tenant,
        account,
        run,
        service_code="electric",
        quantity=Decimal("100"),
        unit="kWh",
        total=Decimal(total),
        **overrides,
    )


# ══════════════════════════════════════════════════════════════════════════
# /totals — the summary's headline, the same figures on every shape
# ══════════════════════════════════════════════════════════════════════════
def test_8809__totals_equal_the_summarys_headline_with_a_credit_a_void_and_a_rebill(
    brazos, dana
):
    """GT-6's $25.00 goodwill credit against $247.30 (OQ-121: $222.30), a void
    that drops out, and a bill corrected to $104.20 in a later run (OQ-111):
    $222.30 + $104.20 = **$326.50** over 2 bills, from both reads."""
    with tenant_ctx(brazos):
        run = a_run(brazos)
        a = an_account(dana, brazos, account_no="A-88091")
        credited = _bill(brazos, a, run, "247.30", status=models.INVOICE_ISSUED)
        models.CreditNote.objects.create(
            tenant=brazos,
            account=a,
            original_invoice=credited,
            credit_note_no="CN-2607-008809",
            amount=Decimal("-25.00"),
            currency="USD",
            reason="goodwill",
        )
        b = an_account(dana, brazos, account_no="A-88092")
        _bill(brazos, b, run, "60.00", status=models.INVOICE_VOID)
        c = an_account(dana, brazos, account_no="A-88093")
        original = _bill(
            brazos, c, run, "117.01", status=models.INVOICE_ISSUED, invoice_no="BL-2607-880930"
        )
        later = a_run(brazos, key="2026-07|cycle-1")
        rebill = _bill(
            brazos,
            c,
            later,
            "104.20",
            status=models.INVOICE_ISSUED,
            invoice_no="BL-2607-880931",
            bill_type="rebill",
            # Stamped at creation: an issued bill takes no later edit but its
            # status (hard rule 4's trigger on PostgreSQL).
            corrects_invoice_id=original.pk,
        )
        assert rebill.corrects_invoice_id == original.pk
        original.status = models.INVOICE_CORRECTED
        original.save(update_fields=["status"])

        totals = release.totals_for(run)
        summary = release.summary_for(run)
        served = api_call(
            billing_api.run_totals,
            "get",
            user=FakeUser(user_id=uuid.uuid4()),
            role="billing_clerk",
            tenant=brazos,
            run_id=str(run.pk),
        )
        panel = api_call(
            billing_api.run_summary,
            "get",
            user=FakeUser(user_id=uuid.uuid4()),
            role="billing_clerk",
            tenant=brazos,
            run_id=str(run.pk),
        )

    assert {key: totals[key] for key in HEADLINE} == _headline(summary)
    assert totals["amount"] == Decimal("326.500000")
    assert totals["bills"] == 2
    assert served.status_code == 200
    assert served.data == {
        "bill_run_id": str(run.pk),
        **{key: panel.data[key] for key in HEADLINE},
    }
    assert served.data["amount"] == "326.500000"


def test_8809__totals_refuse_where_the_summary_refuses(brazos, dana):
    """A `corrected` bill nothing replaces: the panel cannot say what is owed,
    and neither can its headline — the same refusal, word for word."""
    with tenant_ctx(brazos):
        run = a_run(brazos)
        orphan = _bill(
            brazos,
            an_account(dana, brazos, account_no="A-88094"),
            run,
            "117.01",
            status=models.INVOICE_ISSUED,
            invoice_no="BL-2607-880940",
        )
        orphan.status = models.INVOICE_CORRECTED
        orphan.save(update_fields=["status"])
        with pytest.raises(BillingRuleError) as from_summary:
            release.summary_for(run)
        with pytest.raises(BillingRuleError) as from_totals:
            release.totals_for(run)
    assert str(from_totals.value) == str(from_summary.value)


def test_8809__the_totals_route_is_mounted():
    from django.urls import resolve

    run_id = uuid.uuid4()
    assert resolve(f"/api/brazosbend/billing/runs/{run_id}/totals").func is billing_api.run_totals
    assert (
        resolve(f"/api/brazosbend/billing/runs/{run_id}/read-lock").func
        is billing_api.run_read_lock
    )


# ══════════════════════════════════════════════════════════════════════════
# The run read — no snapshot decoded, no meter read counted
# ══════════════════════════════════════════════════════════════════════════
def _a_sent_run(brazos, dana):
    run = a_run(brazos)
    account = an_account(dana, brazos, account_no="A-88095")
    models.Invoice.objects.create(
        tenant=brazos,
        account=account,
        bill_run=run,
        invoice_no="BL-2606-880950",
        bill_type="cycle",
        status=models.INVOICE_ISSUED,
        service_date=date(2026, 6, 30),
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        due_date=date(2026, 7, 21),
        issued_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        subtotal=Decimal("10.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("10.00"),
        currency="USD",
        template_version=1,
        payload_version=1,
        bill_payload={"services": [{"code": "electric", "read_id": str(uuid.uuid4())}]},
    )
    models.BillRunRelease.objects.create(
        tenant=brazos,
        bill_run=run,
        summary={},
        account_count=1,
        bill_count=1,
        total_amount=Decimal("10.0000"),
        currency="USD",
        confirmed_by=getattr(dana, "user", dana),
        confirmed_at=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
        released_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
    )
    return run


def test_8809__a_sent_runs_read_decodes_no_snapshot_and_counts_no_meter_read(brazos, dana):
    """The run read is what tells the page which step it is on, so every screen
    waits for it. On a sent run it read every bill's `services` snapshot and
    counted those reads in Meter Reads; now neither table is touched, and the
    same answer comes from `GET …/read-lock`."""
    with tenant_ctx(brazos):
        run = _a_sent_run(brazos, dana)
        with CaptureQueriesContext(connection) as ctx:
            detail = selectors.run_detail_dict(run)
        lock = selectors.run_read_lock_dict(run)
    touched = [q["sql"] for q in ctx.captured_queries]
    assert not [sql for sql in touched if "bill_payload" in sql], touched
    assert not [sql for sql in touched if "meter_reads" in sql], touched
    assert "meter_reads" not in detail
    assert detail["phase"] == "issued"
    # The read id resolves to no read of this utility, so nothing is counted —
    # Meter Reads' answer, now on its own read.
    assert lock == {
        "bill_run_id": str(run.pk),
        "meter_reads": {"state": "none", "reads": 0, "locked": 0},
    }


# ══════════════════════════════════════════════════════════════════════════
# Not in this run — only the accounts the run holds no bill for
# ══════════════════════════════════════════════════════════════════════════
def test_8809__not_in_run_decides_only_the_accounts_the_run_did_not_bill(
    brazos, dana, monkeypatch
):
    """A-00101 billed, A-00102 blocked, A-00106 left out: two rows, and two
    statuses decided — not three accounts decided twice (six) to skip one."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        check_store.leave_out(run, str(accounts["A-00106"].id))
        _priced(run)
        billed = {
            str(one)
            for one in models.Invoice.objects.filter(bill_run=run).values_list(
                "account_id", flat=True
            )
        }
        full_statuses = check_store.account_statuses(run)
        full_partition = check_store.pricing_partition(run)
        # The old path, with every account's statuses handed in (Sign off's).
        whole = not_in_run.rows_for(run, statuses=full_statuses)

        decided = []
        real_status = check_store._status

        def counting(*args, **kwargs):
            decided.append(args)
            return real_status(*args, **kwargs)

        monkeypatch.setattr(check_store, "_status", counting)
        page = not_in_run.not_in_run(run, {"page": "1", "per": "50"})
        rows = not_in_run.rows_for(run)
        monkeypatch.setattr(check_store, "_status", real_status)
        statuses, partition = check_store.unbilled_statuses_and_partition(run)

    unbilled = set(full_statuses) - billed
    assert billed == {str(accounts["A-00101"].id)}
    assert len(unbilled) == 2
    # One decision per unbilled account per read (the page, then `rows_for`).
    assert len(decided) == 2 * len(unbilled)
    assert rows == whole
    assert [r["account_no"] for r in page["results"]] == [r["account_no"] for r in whole]
    assert statuses == {key: full_statuses[key] for key in unbilled}
    assert partition == {key: v for key, v in full_partition.items() if key in unbilled}
