# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-09-30, option A — the bulk run's check output is kept as
#           long as the bills and LOCKED at Send (decision log, *"WHAT HAPPENS
#           TO THE BULK RUN'S CHECK OUTPUT WHEN THE RUN IS SENT"*).
# Guards:   `check_store.refuse_if_sent` (every database) · `billing/0034`'s
#           trigger (PostgreSQL — the tests marked so are skipped on sqlite,
#           where no trigger exists, and run with `--ds=config.settings.pgtest`)
# ───────────────────────────────────────────────────────
"""At Send a run's check record stops changing, and nothing ever deletes it.

(1) decisions and standing answers — locked;
(2) the account checks — the run's final Check report, locked;
(3) findings — only the final version per account exists (a re-check
    replaces an account's rows), and that version is locked;
(4) no retention job — nothing is deleted afterwards;
(5) the automatic re-check stops for a sent run;
(6) a catch-up run checks afresh in its OWN record;
(7) a read-only Check report is served.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db import DatabaseError, connection, transaction

from apps.billing import check_models, check_staleness, check_store, decisions, pending, runs
from apps.billing import models as billing_models
from apps.billing.exceptions import BillingRuleError

from tests.test_bbr_check_engine import BILL_DATE, PERIOD_END, PERIOD_START, three_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PG_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="billing/0034's trigger exists on PostgreSQL only"
)


def _sent_run(brazos, dana):
    cycle, _plan, accounts = three_accounts(brazos, dana)
    run = runs.create_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=BILL_DATE,
        label="June",
    )
    check_store.check_run(run)
    held = accounts["A-00102"]
    decisions.record_decision(
        bill_run=run,
        account_id=str(accounts["A-00101"].id),
        case="late_fee",
        choice="waive",
        reason="first time",
    )
    decisions.set_standing_answer(bill_run=run, case="possible_rollover", choice="hold")
    runs.mark_for_later(bill_run=run, account_id=str(held.id), reason_code="staff_hold")
    billing_models.BillRunRelease.objects.create(
        tenant=brazos,
        bill_run=run,
        summary={"accounts": 3},
        account_count=3,
        bill_count=2,
        total_amount="0",
        currency="USD",
        confirmed_at=datetime(2026, 7, 1, tzinfo=UTC),
        released_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
    )
    return run, accounts, held


def _count(run):
    return tuple(
        model.objects.filter(bill_run=run).count()
        for model in (
            billing_models.BillRunDecision,
            check_models.BillRunStandingAnswer,
            check_models.BillRunAccountCheck,
            check_models.BillRunFinding,
        )
    )


# BULK-CHG-54
def test_us_bil_037_locked__a_sent_run_refuses_every_write_by_name(brazos, dana):
    with tenant_ctx(brazos):
        run, accounts, _held = _sent_run(brazos, dana)
        before = _count(run)
        assert check_store.run_is_sent(run)
        for attempt in (
            lambda: decisions.record_decision(
                bill_run=run,
                account_id=str(accounts["A-00106"].id),
                case="late_fee",
                choice="apply",
            ),
            lambda: decisions.set_standing_answer(
                bill_run=run, case="possible_rollover", choice="estimate"
            ),
            lambda: check_store.check_run(run),
            lambda: check_store.check_run(run, only_accounts=[str(accounts["A-00101"].id)]),
        ):
            with pytest.raises(BillingRuleError) as refused:
                attempt()
            assert refused.value.message_key == "billing.check.runSent"
        # (5) the automatic re-check stops for a sent run.
        assert check_staleness.sweep(run) == {"stale": 0, "rechecked": 0, "background": False}
        after = _count(run)
    assert before == after and before[2] == 3, "nothing moved, nothing was deleted"


# BULK-CHG-54
def test_us_bil_037_locked__the_check_report_is_served_as_at_send(brazos, dana):
    with tenant_ctx(brazos):
        run, _accounts, _held = _sent_run(brazos, dana)
        report = check_store.check_report(run, {"per": "50"})
    assert report["sent"] is True
    assert report["accounts"]["count"] == 3
    assert [row["account_no"] for row in report["accounts"]["results"]] == [
        "A-00101",
        "A-00102",
        "A-00106",
    ]
    assert report["tiles"]["accounts"] == 3
    assert all("status" in row and "problems" in row for row in report["accounts"]["results"])


# BULK-CHG-54
def test_us_bil_037_locked__a_catch_up_run_checks_afresh_in_its_own_record(brazos, dana):
    with tenant_ctx(brazos):
        run, _accounts, held = _sent_run(brazos, dana)
        parent_before = _count(run)
        child = pending.create_catch_up_run(parent_run=run, account_ids=[str(held.id)])
        check_store.check_run(child)
        child_rows = list(
            check_models.BillRunAccountCheck.objects.filter(bill_run=child).values_list(
                "account_no", flat=True
            )
        )
        parent_after = _count(run)
    assert child_rows == ["A-00102"], "the held account is checked again, by the child"
    assert parent_before == parent_after, "the parent's record is untouched"


# BULK-CHG-54
def test_us_bil_037_locked__only_the_final_findings_version_is_kept(brazos, dana):
    """(3) — a re-check REPLACES an account's rows; no intermediate version stays."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=BILL_DATE,
            label="June",
        )
        check_store.check_run(run)
        one = str(accounts["A-00101"].id)
        first = check_models.BillRunFinding.objects.filter(bill_run=run, account_id=one).count()
        check_store.check_run(run, only_accounts=[one])
        check_store.check_run(run, only_accounts=[one])
        rows = check_models.BillRunAccountCheck.objects.filter(bill_run=run, account_id=one).count()
        again = check_models.BillRunFinding.objects.filter(bill_run=run, account_id=one).count()
    assert rows == 1 and again == first


@PG_ONLY
@pytest.mark.parametrize(
    "model",
    [
        billing_models.BillRunDecision,
        check_models.BillRunStandingAnswer,
        check_models.BillRunAccountCheck,
        check_models.BillRunFinding,
    ],
    ids=["decisions", "standing_answers", "account_checks", "findings"],
)
# BULK-CHG-54
def test_us_bil_037_locked_pg__the_database_refuses_update_and_delete_after_send(
    brazos, dana, model
):
    with tenant_ctx(brazos):
        run, _accounts, _held = _sent_run(brazos, dana)
        rows = model.objects.filter(bill_run=run)
        assert rows.exists(), "the fixture must hold a row to refuse"
        field = {
            billing_models.BillRunDecision: "reason",
            check_models.BillRunStandingAnswer: "choice",
            check_models.BillRunAccountCheck: "status",
            check_models.BillRunFinding: "detail",
        }[model]
        with pytest.raises(DatabaseError) as updated:
            with transaction.atomic():
                rows.update(**{field: "changed after send"})
        with pytest.raises(DatabaseError) as deleted:
            with transaction.atomic():
                model.objects.filter(pk=rows.first().pk).delete()
        remaining = rows.count()
    print(f"\nPROOF lock {model._meta.db_table}: update -> {str(updated.value).splitlines()[0]}")
    assert "is sent" in str(updated.value) and "is sent" in str(deleted.value)
    assert remaining >= 1
