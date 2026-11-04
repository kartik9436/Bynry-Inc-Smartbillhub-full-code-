# ── Trace ──────────────────────────────────────────────
# Stories:  US-BIL-037 TC-14 (Ready to bill: Leave out, Put back) · US-BIL-041
#           TC-1, TC-3, TC-5, TC-7 (Not in this run; catch-up; leave for next
#           cycle; put back before pricing) · US-BIL-040 TC-4 (at Send the
#           accounts not billed are in Pending billing, left-out ones with
#           reason *left out by clerk*)
# Rules:    BR-BIL-1054 · BR-BIL-034 · BR-BIL-015 (catch-up = child run)
# Defects:  DEF-BIL-8217 · DEF-BIL-8223 · DEF-BIL-8410
# Plan:     15-bulk-bill-run-build-plan.md B18, B20, DB3, A9 · T1, T3
# ───────────────────────────────────────────────────────
"""Leave out, Put back, Not in this run, the queue at Send — written red first.

Red against `c0e8cbbe9`: no `check_store.leave_out`, no `not_in_run`, no
`pending.queue_not_in_run` / `leave_for_next_cycle`, no `/check/leave-out`,
`/not-in-run` routes; and a Check-blocked account is never queued at Send.
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime

import pytest

from apps.billing import (
    check_api,
    check_store,
    decisions,
    not_in_run,
    pending,
    runs,
    selectors,
)
from apps.billing import models as billing_models
from apps.billing.exceptions import BillingRuleError

from tests.test_bbr_check_engine import (
    PERIOD_END,
    PERIOD_START,
    reads_without_unit,
    three_accounts,
)
from tests.test_bbr_check_store import a_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db

SENT_AT = datetime(2026, 7, 3, 9, 0, tzinfo=UTC)


def _checked(brazos, dana, monkeypatch):
    """Three accounts: A-00102 BLOCKED (a reading with no unit, none on its
    meter either), A-00101 and A-00106 READY."""
    cycle, plan, accounts = three_accounts(brazos, dana)
    reads_without_unit(monkeypatch, accounts["A-00102"].unit_id, meter_unit=None)
    run = a_run(cycle)
    check_store.check_run(run)
    return run, accounts


def _priced(run):
    prepared = selectors.prepared_for(run)
    runs.calculate_run(decisions.apply_decisions(prepared, bill_run=run), bill_run=run)


# ══════════════════════════════════════════════════════════════════════════
# TC-14 · Leave out / Put back a READY account
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-41
def test_8217_tc14__leave_out_moves_a_ready_account_and_put_back_returns_it(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        a106 = str(accounts["A-00106"].id)
        before = check_store.counts(run)
        check_store.leave_out(run, a106, decided_by=None)
        left = check_store.counts(run)
        listed = check_store.ready_accounts(run, {})
        only = check_store.ready_accounts(run, {"left_out": "only"})
        check_store.put_back(run, a106)
        back = check_store.counts(run)
        check_store.leave_out(run, a106)  # and again — the trail is append-only
        trail = list(
            billing_models.BillRunDecision.objects.filter(
                bill_run=run, account_id=a106, case="left_out"
            ).order_by("created_at")
        )

    assert (before["ready"], before["left_out"]) == (2, 0)
    assert (left["ready"], left["left_out"]) == (1, 1)
    assert listed["left_out"] == 1 and len(listed["results"]) == 2
    assert [r["account_no"] for r in only["results"]] == ["A-00106"]
    assert only["results"][0]["left_out"] is True
    assert (back["ready"], back["left_out"]) == (2, 0)
    assert [(r.choice, r.superseded_by_id is None) for r in trail] == [
        ("leave_out", False),
        ("put_back", False),
        ("leave_out", True),
    ]


# BULK-CHG-41
def test_8217__only_a_ready_account_can_be_left_out(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        with pytest.raises(BillingRuleError) as refused:
            check_store.leave_out(run, str(accounts["A-00102"].id))  # blocked
        with pytest.raises(BillingRuleError) as not_out:
            check_store.put_back(run, str(accounts["A-00101"].id))
    assert refused.value.message_key == "billing.check.leaveOut.notReady"
    assert not_out.value.message_key == "billing.check.putBack.notLeftOut"


# BULK-CHG-41 · BULK-CHG-40
def test_8217_tc7__a_left_out_account_is_not_priced_and_is_queued_as_left_out_by_clerk(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        check_store.leave_out(run, str(accounts["A-00106"].id))
        _priced(run)
        drafted = set(
            billing_models.Invoice.objects.filter(bill_run=run).values_list(
                "account__account_no", flat=True
            )
        )
        row = billing_models.BillRunExclusion.objects.get(bill_run=run, account=accounts["A-00106"])
    assert drafted == {"A-00101"}
    assert row.reason_code == "staff_left_out_by_clerk"
    assert pending.origin_of(row.reason_code) == pending.ORIGIN_PREPARE


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-041 TC-1 · Not in this run lists every account, with its reason
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40 · BULK-CHG-42
def test_8223_tc1__not_in_run_lists_blocked_and_left_out_with_their_reasons(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        check_store.leave_out(run, str(accounts["A-00106"].id))
        listed = not_in_run.not_in_run(run, {})
        blocked_only = not_in_run.not_in_run(run, {"group": "blocked"})

    assert listed["counts"]["accounts"] == 2 and listed["counts"]["units"] == 0
    assert [(r["account_no"], r["group"], r["reason"]) for r in listed["results"]] == [
        ("A-00102", "blocked", "reading_and_meter_have_no_unit"),
        ("A-00106", "left_out", "staff_left_out_by_clerk"),
    ]
    assert [r["account_no"] for r in blocked_only["results"]] == ["A-00102"]
    assert listed["results"][0]["queue"] is None  # not sent: nothing queued yet


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-040 TC-4 · at Send, every account not billed enters Pending billing
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40
def test_8410__at_send_a_blocked_account_enters_pending_billing_and_can_be_caught_up(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        _priced(run)
        a102 = accounts["A-00102"]
        assert pending.held_account_ids(run) == frozenset(), "nothing queued before Send"
        written = pending.queue_not_in_run(bill_run=run)
        again = pending.queue_not_in_run(bill_run=run)
        row = billing_models.BillRunExclusion.objects.get(bill_run=run, account=a102)
        child = pending.create_catch_up_run(parent_run=run, account_ids=[str(a102.id)])
        listed = not_in_run.not_in_run(run, {"as_of": "2026-07-05"})

    assert (written, again) == (1, 0), "one row, and idempotent"
    assert (row.reason_code, row.detail) == ("check_blocked", "reading_and_meter_have_no_unit")
    assert child.parent_run_id == run.pk and child.period_start == PERIOD_START
    [queued] = [r for r in listed["results"] if r["account_no"] == "A-00102"]
    assert queued["queue"]["reason_code"] == "check_blocked"
    assert queued["queue"]["age_days"] >= 0


# BULK-CHG-40
def test_8410__issue_queues_the_not_in_run_accounts_after_it_resolves_the_queue():
    """Wiring (hard-won law 2): every issue pass calls it, once, at the end.

    Since 2.426.0 (`DEF-BIL-8726`) the run-wide close lives in
    `issue.finish_issue_pass`, which `issue_run` calls at its end and the
    batched Send (`send_batches._complete`) calls once after its last batch —
    so the wiring is asserted on all three, not on `issue_run`'s text alone."""
    from apps.billing import issue, send_batches

    close = inspect.getsource(issue.finish_issue_pass)
    assert "pending.queue_not_in_run(bill_run=bill_run, actor=actor)" in close
    assert close.index("pending.resolve_for_run(") < close.index("pending.queue_not_in_run(")
    tail = inspect.getsource(issue.issue_run)
    assert "finish_issue_pass(bill_run=bill_run, issued_at=issued_at, actor=actor)" in tail
    assert "issue.finish_issue_pass(" in inspect.getsource(send_batches._complete)


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-041 TC-5 / TC-6 · Leave for next cycle — closed by a LATER run
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40
def test_8223_tc5__leave_for_next_cycle_marks_the_row_and_a_later_run_closes_it(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        _priced(run)
        pending.queue_not_in_run(bill_run=run)
        a102 = accounts["A-00102"]
        with pytest.raises(BillingRuleError):
            pending.leave_for_next_cycle(
                bill_run=run, account_ids=[str(accounts["A-00101"].id)], at=SENT_AT
            )
        marked = pending.leave_for_next_cycle(bill_run=run, account_ids=[str(a102.id)], at=SENT_AT)
        [queued] = [
            r for r in pending.pending_rows(as_of=date(2026, 7, 5)) if r.account_id == str(a102.id)
        ]
        # The July run bills A-00102 (its unit fixed): a draft on a LATER period.
        july = runs.create_run(
            cycle_id=run.cycle_id,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            bill_date=date(2026, 8, 1),
            label="July",
        )
        billing_models.Invoice.objects.create(
            tenant=brazos,
            account=a102,
            bill_run=july,
            service_date=date(2026, 7, 31),
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            status=billing_models.INVOICE_ISSUED,
            currency="USD",
            subtotal=0,
            tax_total=0,
            total=0,
        )
        closed = pending.resolve_for_run(bill_run=july, resolved_at=SENT_AT)
        row = billing_models.BillRunExclusion.objects.get(bill_run=run, account=a102)

    assert marked == 1 and queued.next_cycle is True
    assert closed == 1 and row.resolved_by_run_id == july.pk


# ══════════════════════════════════════════════════════════════════════════
# T3 · the routes
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-41 · BULK-CHG-40
def test_t3__leave_out_put_back_and_not_in_run_routes(brazos, lonestar, dana, monkeypatch):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        clerk = an_actor_user(brazos)
    a106 = str(accounts["A-00106"].id)

    def call(view, method, data=None, query=None, user=clerk, role="billing_clerk", tenant=brazos):
        return api_call(
            view,
            method,
            user=user,
            role=role,
            tenant=tenant,
            data=data,
            query=query,
            run_id=str(run.pk),
        )

    left = call(check_api.run_leave_out, "post", {"account_ids": [a106]})
    assert left.status_code == 201 and left.data["counts"]["left_out"] == 1
    refused = call(check_api.run_leave_out, "post", {"account_ids": [str(accounts["A-00102"].id)]})
    assert refused.status_code == 422
    listed = call(check_api.run_not_in_run, "get", query={"group": "left_out"}, user=FakeUser())
    assert [r["account_no"] for r in listed.data["results"]] == ["A-00106"]
    back = call(check_api.run_put_back, "post", {"account_ids": [a106]})
    assert back.status_code == 201 and back.data["counts"]["left_out"] == 0
    viewer = call(
        check_api.run_leave_out, "post", {"account_ids": [a106]}, user=FakeUser(), role="executive"
    )
    assert viewer.status_code == 403
    assert (
        call(check_api.run_not_in_run, "get", user=FakeUser(), tenant=lonestar).status_code == 404
    )
    assert (
        call(
            check_api.run_leave_for_next_cycle,
            "post",
            {"account_ids": [a106], "at": "2026-07-03T09:00:00+00:00"},
        ).status_code
        == 422
    ), "not waiting in Pending billing"
    assert PERIOD_END  # the fixture's period (kept for the reader)



# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8413 · a held month billed by the next cycle is no longer owed
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-50
def test_8413__a_later_bill_that_covers_the_held_month_closes_its_row(brazos, dana, monkeypatch):
    """Fixed-charge case 3: a held account's next bill starts the day after its
    last bill — here June 1 — so it bills June. Its June queue row closes, and
    no catch-up can bill June again. A July bill for July alone does not."""
    with tenant_ctx(brazos):
        run, accounts = _checked(brazos, dana, monkeypatch)
        _priced(run)
        pending.queue_not_in_run(bill_run=run)
        a102 = accounts["A-00102"]

        def a_later_bill(month, start, label):
            later = runs.create_run(
                cycle_id=run.cycle_id,
                period_start=date(2026, month, 1),
                period_end=date(2026, month, 28),
                bill_date=date(2026, month + 1, 1),
                label=label,
            )
            billing_models.Invoice.objects.create(
                tenant=brazos,
                account=a102,
                bill_run=later,
                service_date=date(2026, month, 28),
                period_start=start,
                period_end=date(2026, month, 28),
                status=billing_models.INVOICE_ISSUED,
                currency="USD",
                subtotal=0,
                tax_total=0,
                total=0,
            )
            return later

        only_july = a_later_bill(7, date(2026, 7, 1), "July only")
        kept = pending.resolve_for_run(bill_run=only_july, resolved_at=SENT_AT)
        both = a_later_bill(8, date(2026, 6, 1), "June to August")
        closed = pending.resolve_for_run(bill_run=both, resolved_at=SENT_AT)
        row = billing_models.BillRunExclusion.objects.get(bill_run=run, account=a102)
        with pytest.raises(BillingRuleError):
            pending.create_catch_up_run(parent_run=run, account_ids=[str(a102.id)])

    assert kept == 0, "a July bill for July leaves June owed"
    assert closed == 1 and row.resolved_by_run_id == both.pk
