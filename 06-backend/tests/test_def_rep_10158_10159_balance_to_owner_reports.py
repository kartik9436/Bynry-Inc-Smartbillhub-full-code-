# ── Trace ──────────────────────────────────────────────
# Defects: DEF-REP-10158 (the Owner summary leaves out a balance moved to the
#          owner) · DEF-REP-10159 (Receivables by service names the departed
#          tenant after the move). Found by the combined walk 2026-10-14,
#          steps 7 and 9.
# Code:    apps/ledger/reporting.balance_to_owner_moves (the one read) ·
#          apps/payments/receivables_by_service.apply_balance_moves ·
#          apps/reports/owner_summary (`moved_from_tenants`, `in_the_books`)
# Rule:    decision log 2026-10-14 *"A BALANCE MOVED TO THE OWNER CARRIES THE
#          TENANT'S BILL SHARES WITH IT"*
# ───────────────────────────────────────────────────────
"""A tenant moves out owing $365.21 and the balance is tied back to the owner.

The walk's own figures. The tenant (AC-2026-00044) owes two bills — **$344.26**
(water 200.00 + electric 144.26, due 2026-06-30) and the final bill **$20.95**
(water 11.00 + sewer 9.95, due 2026-11-20). Mill Pond Apartments LP's owner
account (AC-2026-00053) was billed **$2.00** in the period (a paper fee). On
2026-11-02 the $365.21 moves: DR AR owner / CR AR tenant, one journal entry
(CR-185 D5), and no bill changes.

  * **DEF-REP-10159** — Receivables by service as at 2027-03-31 named the
    TENANT owing $365.21 and the owner $2.00; the books say tenant $0.00, owner
    $367.21. After: the tenant is on no row and the owner owes the tenant's
    shares — water 211.00, electric 144.26, sewer 9.95 — beside its own $2.00.
  * **DEF-REP-10158** — the Owner summary for 10/01–11/30 read **$2.00**. After:
    *Moved from tenants* **$365.21**, grand total **$367.21**, and *In the
    books* **$367.21** beside it — it foots, and when the owner has paid
    something it says by how much it differs instead.

RED PROVED (2026-10-14, SQLite, in pytest): the tip's `receivables_by_service.py`
and `owner_summary.py` put back under these cases → **7 failed, 2 passed**:
  * `test_the_owner_owes_the_tenants_shares_after_the_move` —
    `'AC-2026-00044' not in {'AC-2026-00044': {'water': 211.000000, 'electric':
    144.260000, 'sewer': 9.950000}, 'AC-2026-00053': {'fees': 2.000000}}`;
  * `test_the_owner_carries_the_tenant_bills_age` — `debtors_over_90 2 == 1`;
  * `test_the_owner_summary_shows_the_move_and_foots_to_the_books` —
    `KeyError: 'moved_from_tenants'`.
The two that pass either side (before the book date; a reversed move) rule out
a fix that moves balances it should not.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.ledger import balance_transfer, chart, models as ledger_models, posting, selectors
from apps.ledger import reporting as ledger_reporting
from apps.payments import receivables_by_service as rbs
from apps.payments.outstandings import AGEING_BANDS
from apps.reports import owner_summary, runner

from tests.test_cr184_receivables_by_service import _bill as ar_bill
from tests.test_cr185_owner_summary_report import _holder, _master
from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
D = Decimal
ZERO = D("0")
MOVED_ON = date(2026, 11, 2)
AS_OF = date(2027, 3, 31)
WINDOW = {"from": "2026-10-01", "to": "2026-11-30"}


def _post(account, amount, *, side, key, entry_date, other="opening_clearing"):
    """One balanced entry on `account`'s AR through the posting service."""
    ar = selectors.gl_account_id_for_designation(chart.AR)
    contra = selectors.gl_account_id_for_designation(other)
    flip = ledger_models.SIDE_CREDIT if side == ledger_models.SIDE_DEBIT else ledger_models.SIDE_DEBIT
    return posting.post(
        posting.PostingRequest(
            posting_key=posting.posting_key(source_type="opening_balance", source_id=account.id,
                                            event=key),
            entry_date=entry_date,
            posted_at=datetime.combine(entry_date, datetime.min.time(), tzinfo=UTC),
            currency="USD",
            source_type="opening_balance",
            source_id=account.id,
            lines=(
                posting.PostingLine(ledger_account_id=ar, side=side, amount=amount,
                                    source_type="opening_balance", source_id=account.id,
                                    account_id=account.id),
                posting.PostingLine(ledger_account_id=contra, side=flip, amount=amount,
                                    source_type="opening_balance", source_id=account.id,
                                    account_id=account.id),
            ),
        )
    )


def _mill_pond(tenant, actor):
    """The owner, its $2.00 bill in the period, and the tenant's two bills —
    each in the books the way an issued bill is (DR AR)."""
    owner = _master(tenant, actor, "301 Mill Pond Ln", "AC-2026-00053")
    _holder(tenant, "Mill Pond Apartments LP", [owner])
    paper = ar_bill(tenant, owner, no="BL-2611-000300", due=date(2026, 11, 20),
                    issued=datetime(2026, 11, 2, 9, 0, tzinfo=UTC),
                    lines=[(None, "fee", D("2.00"))])
    _post(owner, D("2.00"), side=ledger_models.SIDE_DEBIT, key="paper", entry_date=MOVED_ON)

    leaving = an_account(tenant, actor, account_no="AC-2026-00044", label="Apt 104",
                         service="water")
    ar_bill(tenant, leaving, no="BL-2606-000100", due=date(2026, 6, 30),
            issued=datetime(2026, 6, 5, 9, 0, tzinfo=UTC),
            lines=[("water", "usage", D("200.00")), ("electric", "usage", D("144.26"))])
    ar_bill(tenant, leaving, no="BL-2611-000342", due=date(2026, 11, 20),
            issued=datetime(2026, 11, 2, 9, 0, tzinfo=UTC),
            lines=[("water", "usage", D("11.00")), ("sewer", "usage", D("9.95"))])
    _post(leaving, D("365.21"), side=ledger_models.SIDE_DEBIT, key="bills", entry_date=MOVED_ON)
    return owner, leaving, paper


def _move(leaving, owner, amount=D("365.21")):
    return balance_transfer.post_balance_to_owner(
        from_account_id=leaving.id, to_account_id=owner.id, amount=amount,
        entry_date=MOVED_ON, posted_at=datetime(2026, 11, 2, 15, 0, tzinfo=UTC), currency="USD",
    )


def _by_account(dataset):
    out: dict[str, dict] = {}
    for row in dataset["rows"]:
        out.setdefault(row.account_no, {})[row.service_code or row.charge_class] = row.total
    return out


def _books(*accounts):
    found = ledger_reporting.ar_positions(account_ids=[str(a.id) for a in accounts])["positions"]
    return [found.get(str(a.id), ZERO) for a in accounts]


# ═════════════════════════════════════════════════════════════════════════
# DEF-REP-10159 — RECEIVABLES BY SERVICE
# ═════════════════════════════════════════════════════════════════════════
def test_the_owner_owes_the_tenants_shares_after_the_move(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        before = rbs.receivables_dataset(as_of=AS_OF, per=None)
        _move(leaving, owner)
        assert _books(leaving, owner) == [D("0"), D("367.21")]

        after = rbs.receivables_dataset(as_of=AS_OF, per=None)
        rows = _by_account(after)
        assert "AC-2026-00044" not in rows
        assert rows["AC-2026-00053"] == {
            "water": D("211.0000"),
            "electric": D("144.2600"),
            "sewer": D("9.9500"),
            "fees": D("2.00"),
        }
        assert sum(rows["AC-2026-00053"].values()) == D("367.21")
        # Moved, not created: the whole and the foot figure are unchanged.
        assert after["population"] == before["population"] == D("367.21")
        assert after["totals"]["total"] == before["totals"]["total"]
        assert after["totals"]["accounts"] == 1
        assert after["population_accounts"] == 1


def test_the_owner_carries_the_tenant_bills_age(brazos, dana):
    """The June bill's share is over 90 days on the owner's row too."""
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        _move(leaving, owner)
        report = rbs.over_90_by_service(as_of=AS_OF)
        by_row = {(r.service_code or r.charge_class): r for r in report["rows"]}
        assert by_row["electric"].over_90 == D("144.2600")
        assert by_row["water"].over_90 == D("211.0000")  # both water bills are > 90 days by 3/31
        assert by_row["electric"].debtors == 1
        assert report["debtors_over_90"] == 1
        assert report["total"] == report["population"] == D("367.21")


def test_before_the_book_date_the_tenant_still_owes(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        _move(leaving, owner)
        rows = _by_account(rbs.receivables_dataset(as_of=date(2026, 11, 1), per=None))
        # The move is dated 11/02; on 11/01 it had not happened. (The 11/02
        # bills are not issued yet either, so only the June bill is open.)
        assert rows == {"AC-2026-00044": {"water": D("200.00"), "electric": D("144.26")}}


def test_a_part_move_settles_the_oldest_bill_first_in_proportion(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        _move(leaving, owner, amount=D("100.00"))
        rows = _by_account(rbs.receivables_dataset(as_of=AS_OF, per=None))
        # 100.00 of the June bill (200.00 : 144.26) → water 58.0956, electric 41.9044.
        assert rows["AC-2026-00053"]["water"] + rows["AC-2026-00053"]["electric"] == D("100.00")
        assert rows["AC-2026-00053"]["water"] == D("58.0956")
        assert rows["AC-2026-00053"]["electric"] == D("41.9044")
        assert rows["AC-2026-00044"] == {
            "water": D("200.00") - D("58.0956") + D("11.00"),
            "electric": D("144.26") - D("41.9044"),
            "sewer": D("9.95"),
        }
        assert sum(rows["AC-2026-00044"].values()) == D("265.21")


def test_a_move_larger_than_the_open_bills_is_counted_never_placed():
    tenant_id, owner_id = "a", "b"
    bill = rbs.SharedBill(
        invoice_id="i1", account_id=tenant_id, due_date=date(2026, 6, 30), currency="USD",
        owed=D("10.00"), band="90+",
        share=rbs.BillShare(shares={("water", None): D("10.00")}, method=rbs.METHOD_UNPAID),
    )
    run = rbs.ShareRun()
    move = rbs.BalanceMove(from_account_id=tenant_id, to_account_id=owner_id,
                           amount=D("25.00"), entry_date=MOVED_ON)
    out = list(rbs.apply_balance_moves([bill], (move,), run=run))
    assert [(b.account_id, b.owed) for b in out] == [(owner_id, D("10.00"))]
    assert run.moved_without_a_bill == D("15.00")
    assert run.problems()[0]["code"] == "balance_moved_to_owner_without_an_open_bill"


def test_a_reversed_move_moves_nothing(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        _move(leaving, owner)
        # A hand-posted mirror of the transfer (same source) nets it away.
        ar = selectors.gl_account_id_for_designation(chart.AR)
        posting.post(posting.PostingRequest(
            posting_key="transfer|%s|balance_to_owner_reversal" % leaving.id,
            entry_date=date(2026, 11, 3), posted_at=datetime(2026, 11, 3, tzinfo=UTC),
            currency="USD", source_type="transfer", source_id=leaving.id,
            reversal_of_id=ledger_models.JournalEntry.objects.get(
                posting_key=balance_transfer.posting_key_for(leaving.id)).id,
            lines=(
                posting.PostingLine(ledger_account_id=ar, side=ledger_models.SIDE_CREDIT,
                                    amount=D("365.21"), source_type="transfer",
                                    source_id=leaving.id, account_id=owner.id),
                posting.PostingLine(ledger_account_id=ar, side=ledger_models.SIDE_DEBIT,
                                    amount=D("365.21"), source_type="transfer",
                                    source_id=leaving.id, account_id=leaving.id),
            ),
        ))
        assert ledger_reporting.balance_to_owner_moves() == ()
        rows = _by_account(rbs.receivables_dataset(as_of=AS_OF, per=None))
        assert sum(rows["AC-2026-00044"].values()) == D("365.21")


# ═════════════════════════════════════════════════════════════════════════
# DEF-REP-10158 — THE OWNER SUMMARY
# ═════════════════════════════════════════════════════════════════════════
def _summary(owner):
    return runner.run(owner_summary.KEY, {**WINDOW, "subject_id": str(owner.id)}).payload


def test_the_owner_summary_shows_the_move_and_foots_to_the_books(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        assert D(_summary(owner)["totals"]["total"]) == D("2.00")
        _move(leaving, owner)

        payload = _summary(owner)
        row = payload["rows"][0]
        assert row["property"] == "301 Mill Pond Ln"
        assert D(row["other_charges"]) == D("2.00")
        assert D(row["moved_from_tenants"]) == D("365.21")
        assert D(row["total"]) == D("367.21")
        assert D(payload["totals"]["moved_from_tenants"]) == D("365.21")
        assert D(payload["totals"]["total"]) == D("367.21")
        kpis = {kpi["key"]: kpi for kpi in payload["kpis"]}
        assert D(kpis["grand_total"]["value"]) == D("367.21")
        assert D(kpis["in_the_books"]["value"]) == D("367.21")
        assert payload["unavailable"] == []
        assert "moved_from_tenants" in payload["columns"]


def test_a_move_outside_the_window_is_not_in_it(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        _move(leaving, owner)
        payload = runner.run(
            owner_summary.KEY,
            {"from": "2026-12-01", "to": "2026-12-31", "subject_id": str(owner.id)},
        ).payload
        assert D(payload["totals"]["moved_from_tenants"]) == D("0")
        # Nothing charged in December, $367.21 owed in the books: stated.
        assert payload["unavailable"][0]["code"] == "owner_summary_differs_from_the_books"
        assert "367.21" in payload["unavailable"][0]["detail"]


def test_when_the_owner_has_paid_the_summary_states_the_difference(brazos, dana):
    with tenant_ctx(brazos):
        owner, leaving, _ = _mill_pond(brazos, dana)
        _move(leaving, owner)
        _post(owner, D("2.00"), side=ledger_models.SIDE_CREDIT, key="paid",
              entry_date=date(2026, 11, 10), other="undeposited_funds")
        payload = _summary(owner)
        kpis = {kpi["key"]: kpi for kpi in payload["kpis"]}
        assert D(kpis["grand_total"]["value"]) == D("367.21")
        assert D(kpis["in_the_books"]["value"]) == D("365.21")
        gap = payload["unavailable"][0]
        assert gap["code"] == "owner_summary_differs_from_the_books"
        assert "-2.00" in gap["detail"]
        assert customer_models.Account.objects.get(pk=owner.pk).kind == "master"
