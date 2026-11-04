# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-10125 (a reopened account's earlier move-out left the
#          Move-outs list) · DEF-CUS-10126 (cancelling a move-in that reopened
#          an account lost the earlier tenancy's dates)
# Change:  CR-181-BRC10 (reopen at move-in, 2.579.0) — decision log *"THE 77
#          OPEN TASKS FROM ROUNDS 1–3"* item 3, no product decision needed
# Rules:   BR-CUS-152 (records are never updated) · CLAUDE.md hard rules 1, 4,
#          7 · hard-won law 14 (run on PostgreSQL too:
#          `--ds=config.settings.pgtest --create-db`)
# ───────────────────────────────────────────────────────
"""**Viktor Valdez moved out on 31 July, came back on 1 September, and then
the move-in was called off.**

THE WORKED CASE (the CR-181 suite's own fixture): Viktor's account was opened
on 1 March 2026 and closed by a move-out on 31 July, owing **$84.20**. On 1
September the clerk reopens it at move-in and carries the $84.20.

* DEF-CUS-10125 — the Move-outs list must still show **his 31 July move-out**
  after the reopen. Before the fix it vanished: the list read `closed_at`, and
  the reopen cleared it.
* DEF-CUS-10126 — cancelling that move-in must give the account back **opened
  1 March, closed 31 July**, closed status. Before the fix it closed the account
  on **31 August, opened 1 September** — the earlier tenancy's dates were gone
  from the row and the whole account read as a cancelled move-in.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting the
response instead of the rows (every case reads the account back); a list that
shows the row because the account is closed again (the cancel case asserts
exactly ONE row for the account, so a duplicate fails too); a row found by a
filter that matches everything (the search and window cases each assert a
miss as well as a hit).
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.customers import models as customers_models
from apps.customers import move_in_cancel, move_in_list, move_in_reopen, move_reads, moves
from apps.customers import services as customers_services
from core import errors

from tests.test_cr181_returning_customer_reopen import _payload, _viktor_moved_out
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CLOSED = "2026-07-31"


def _rows_for(account_no, **kwargs):
    listed = move_reads.move_outs_list(per=100, **kwargs)
    return [row for row in listed["rows"] if row["account_no"] == account_no], listed


def _reopen(dana, unit, account, viktor):
    return customers_services.move_in_to_unit(
        dana,
        unit["id"],
        _payload(viktor, reopen_account_id=account["id"], reopen_balance="carry"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10125 · THE EARLIER MOVE-OUT STAYS ON THE LIST
# ═══════════════════════════════════════════════════════════════════════════
def test_the_earlier_move_out_stays_on_the_list_after_the_reopen(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        before, _ = _rows_for(account["account_no"])
        assert [row["move_out_date"] for row in before] == [CLOSED]

        _reopen(dana, unit, account, viktor)
        assert customers_models.Account.objects.get(pk=account["id"]).closed_at is None

        (row,), listed = _rows_for(account["account_no"])
    assert row["move_out_date"] == CLOSED
    assert row["state"] == move_reads.MOVE_OUT_STATE_CLOSED
    assert row["row_kind"] == move_reads.ROW_KIND_REOPENED_MOVE_OUT
    assert row["account_id"] == str(account["id"])
    assert row["customer"]
    # The live account's books are the NEW tenancy's — withheld, and said so.
    assert row["settlement"]["outstanding"]["stored"] is None
    assert row["settlement"]["deposit_held"]["stored"] is None
    codes = [gap["code"] for gap in row["settlement"]["unavailable"]]
    assert "account_reopened_since_this_move_out" in codes
    # The row is counted in the page's total, so pagination cannot drop it.
    assert listed["total"] >= 1


def test_the_reopened_move_out_answers_search_and_the_closed_window(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        _reopen(dana, unit, account, viktor)
        hit, _ = _rows_for(account["account_no"], q=account["account_no"])
        miss, _ = _rows_for(account["account_no"], q="ZZ-NOBODY-9999")
        in_window, _ = _rows_for(
            account["account_no"], filters={"closed": "last30"}, as_of=date(2026, 8, 15)
        )
        out_of_window, _ = _rows_for(
            account["account_no"], filters={"closed": "last7"}, as_of=date(2026, 8, 15)
        )
    assert [row["move_out_date"] for row in hit] == [CLOSED]
    assert miss == []
    assert [row["move_out_date"] for row in in_window] == [CLOSED]
    assert out_of_window == []


def test_the_reopened_move_out_carries_its_own_move_out_record(brazos, dana):
    """Where the wizard wrote a move-out RECORD, the row's reference is that
    record — not the reopening move-in's number."""
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        record = moves.record_move(
            actor=dana,
            kind=moves.KIND_MOVE_OUT,
            account_id=account["id"],
            effective_on=date.fromisoformat(CLOSED),
        )
        assert record["move_no"], record
        _reopen(dana, unit, account, viktor)
        (row,), _ = _rows_for(account["account_no"])
    assert row["move_no"] == record["move_no"]


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10126 · CANCEL GIVES THE EARLIER TENANCY BACK
# ═══════════════════════════════════════════════════════════════════════════
def test_cancel_restores_the_earlier_tenancy_dates(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        old_agreements = sorted(
            customers_models.ServiceAgreement.objects.filter(account_id=account["id"]).values_list(
                "id", "started_on", "ended_on"
            )
        )
        result = _reopen(dana, unit, account, viktor)
        record = moves.MoveRecord.objects.get(pk=result["move_record_id"])

        preview = move_in_cancel.preview(record.move_no)
        assert preview["allowed"] is True, preview["refusal"]
        assert preview["reverses"]["account"]["closes_on"] == CLOSED

        answer = move_in_cancel.cancel(dana, record.move_no)

        row = customers_models.Account.objects.select_related("status").get(pk=account["id"])
        assert row.opened_at == date(2026, 3, 1)
        assert row.closed_at == date(2026, 7, 31)
        assert row.status.behavior_class == customers_services.CLASS_TERMINAL
        assert answer["account"]["closed_at"] == CLOSED
        assert answer["account"]["opened_at"] == "2026-03-01"
        assert answer["account"]["restored_previous_tenancy"] is True
        # The earlier tenancy's agreements untouched; the move-in's own one
        # ended the day before it started.
        for pk, started, ended in old_agreements:
            again = customers_models.ServiceAgreement.objects.get(pk=pk)
            assert (again.started_on, again.ended_on) == (started, ended)
        (new,) = customers_models.ServiceAgreement.objects.filter(
            account_id=account["id"], started_on=date(2026, 9, 1)
        )
        assert new.ended_on == date(2026, 8, 31)

        # The move-in reads Cancelled — on its own and in the list's SQL.
        assert move_in_list.status_of_record(record, row) == move_in_list.STATUS_CANCELLED
        assert move_in_cancel.record_is_cancelled(record, row) is True
        # The move-in keeps ITS date (1 September), though the account now
        # carries the earlier tenancy's 1 March start (found on the walk).
        from apps.customers import move_record_reads

        assert move_record_reads.move_in_date_of(record, row) == date(2026, 9, 1)
        mine = [
            r for r in move_in_list.move_ins_list(per=100)["rows"] if r.get("move_no") == record.move_no
        ]
        assert [(r["move_in_date"], r["status"]) for r in mine] == [
            ("2026-09-01", move_in_list.STATUS_CANCELLED)
        ]
        assert move_in_cancel.preview(record.move_no)["refusal"]["code"] == (
            move_in_cancel.ALREADY_CANCELLED
        )
        with pytest.raises(errors.BizError) as again_refused:
            move_in_cancel.cancel(dana, record.move_no)
        assert again_refused.value.message_key == "customers.moveIn.cancel.alreadyCancelled"

        # The 31 July move-out is on the Move-outs list ONCE — as the account's
        # own close again, never twice.
        rows, _ = _rows_for(account["account_no"])
        assert [(r["move_out_date"], r["row_kind"]) for r in rows] == [
            (CLOSED, move_reads.ROW_KIND_ACCOUNT)
        ]
        # And the account is an ordinary closed account: offered again.
        offer = move_in_reopen.offer_for(unit["id"], viktor.id)
        assert offer is not None and offer["eligible"] is True
        assert offer["closed_at"] == CLOSED


def test_cancel_of_a_new_account_move_in_still_closes_the_day_before(brazos, dana):
    """The unchanged half: a move-in that opened a NEW account is not touched
    by the reopen branch."""
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos, owed=None)
        result = customers_services.move_in_to_unit(dana, unit["id"], _payload(viktor))
        assert result["id"] != str(account["id"])
        record = moves.MoveRecord.objects.get(pk=result["move_record_id"])
        answer = move_in_cancel.cancel(dana, record.move_no)
        fresh = customers_models.Account.objects.get(pk=result["id"])
    assert fresh.closed_at == date(2026, 8, 31)
    assert fresh.opened_at == date(2026, 9, 1)
    assert answer["account"]["restored_previous_tenancy"] is False
