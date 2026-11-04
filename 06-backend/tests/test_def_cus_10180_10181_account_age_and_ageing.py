# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CUS-10180 (no account age on the Accounts list) ·
#           DEF-CUS-10181 (Aging ignored overdue bills)
# Ruling:   decision log 2026-10-17 — "ACCOUNT AGE ON THE ACCOUNTS LIST; AGING
#           STAYS MONEY AND IS FIXED TO READ BILLS" (PO: "this si all correct -
#           fix it")
# Rules:    BR-CUS-016 · BR-CUS-048 · BR-PAY-032 · NFR-3 · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""The Accounts list's Account age and Aging, against the PO's worked figures.

RED FIRST (hard-won law 7), through pytest: at the base commit `account_age`
and `ageing` are not in `ACCOUNT_SORTS` (the sort falls back to `created`),
a bill-only debtor's `ageing_segment` is None and `f.ageing=d61_90` returns
nothing, and the import accepts a future Opened date.

Run on PostgreSQL as well as SQLite (hard-won law 14): the anchor is a `CASE`
over dates and a correlated subquery, and the two backends compare dates
differently enough that only both runs prove it.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import import_writer, move_in_reopen, seams, selectors
from apps.customers import models as customers_models
from apps.payments import models as payment_models
from apps.payments import outstandings

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

BUCKETS = customers_models.AccountOpeningBucket
CURRENT, D31_60, D61_90, D90_PLUS = BUCKETS.BUCKETS


class FakeUser:
    is_authenticated = True
    id = None
    pk = None
    role = "system_admin"


def _list(tenant, **query):
    response = api_call(
        customers_api.accounts,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        query=query,
    )
    assert response.status_code == 200, response.status_code
    return response.data


def _today(tenant):
    """The tenant's own today, asked INSIDE its context (BR-TEN-003 refuses it
    outside one, which is what the first PostgreSQL run of this file caught)."""
    with tenant_ctx(tenant):
        return seams.tenant_today()


def _ids(payload):
    return [row["id"] for row in payload["results"]]


def _bill(tenant, account, *, number, total, due):
    return an_issued_bill(
        tenant,
        account,
        number=number,
        total=Decimal(total),
        issued_on=due - timedelta(days=20),
        due_date=due,
    )


def _pay_in_full(tenant, account, bill):
    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=bill.total,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=bill.issued_at,
    )
    payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=bill, amount=bill.total
    )


def _opening(account, *, cutover, **amounts):
    mapped = {"ob_current": "0", "ob_31_60": "0", "ob_61_90": "0", "ob_90_plus": "0"}
    mapped.update(amounts)
    import_writer.write_opening_buckets(
        account_id=account.id,
        account_ref=account.account_no,
        mapped=mapped,
        as_of=cutover,
        currency="USD",
    )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10181 · AGING READS THE BILLS
# ═══════════════════════════════════════════════════════════════════════════
def test_the_pos_worked_figure__a_bill_due_0801_unpaid_on_1017_is_61_90(brazos, dana):
    """PO, verbatim: *"a bill due 08/01/2026 unpaid on 10/17/2026 = 77 days →
    61–90 (today it shows "—")"*."""
    as_of = date(2026, 10, 17)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AGE-77")
        _bill(brazos, account, number="BL-AGE-77", total="120.00", due=date(2026, 8, 1))
        segment, days = selectors.ageing_segments_for([account.id], as_of=as_of)[str(account.id)]
        assert (segment, days) == (D61_90, 77)
        cells = selectors.ageing_cells(account.id, selectors._ageing_for([account.id], as_of))
        assert cells["ageing_source"] == "bills"
        assert cells["ageing_unavailable"] is None


def test_the_band_is_the_same_figure_who_owes_you_uses(brazos, dana):
    """One computation, two screens: the list's days are Who owes you's days
    late, and the band is that screen's band folded into BR-CUS-048's four."""
    as_of = date(2026, 10, 17)
    fold = {"current": CURRENT, "1-30": CURRENT, "31-60": D31_60, "61-90": D61_90, "90+": D90_PLUS}
    with tenant_ctx(brazos):
        accounts = []
        for index, late in enumerate((-5, 0, 30, 31, 60, 61, 90, 91, 400)):
            account = an_account(dana, brazos, account_no=f"AGE-W{index}")
            _bill(
                brazos,
                account,
                number=f"BL-W{index}",
                total="10.00",
                due=as_of - timedelta(days=late),
            )
            accounts.append(account)
        mine = selectors.ageing_segments_for([a.id for a in accounts], as_of=as_of)
        view = outstandings.outstandings(as_of=as_of, per=None)
        theirs = {row.account_id: row for row in view.rows}
        for account in accounts:
            row = theirs[str(account.id)]
            segment, days = mine[str(account.id)]
            assert days == max(row.days_late, 0)
            assert segment == fold[row.bucket]


def test_a_balance_not_yet_due_is_current(brazos, dana):
    as_of = date(2026, 10, 17)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AGE-NYD")
        _bill(brazos, account, number="BL-NYD", total="40.00", due=date(2026, 11, 1))
        assert selectors.ageing_segments_for([account.id], as_of=as_of)[str(account.id)] == (
            CURRENT,
            0,
        )


def test_a_zero_balance_is_a_dash_not_current(brazos, dana):
    """Paid in full → null, the screen's `—`. And no reason is attached: since
    the bill half is wired, a null is an answer."""
    as_of = date(2026, 10, 17)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AGE-PAID")
        bill = _bill(brazos, account, number="BL-PAID", total="75.00", due=date(2026, 8, 1))
        _pay_in_full(brazos, account, bill)
        assert selectors.ageing_segments_for([account.id], as_of=as_of) == {}
        cells = selectors.ageing_cells(account.id)
        assert cells["ageing_segment"] is None
        assert cells["ageing_unavailable"] is None


def test_an_older_opening_bucket_wins_over_the_first_bill(brazos, dana):
    """`90+` migrated on 08/31, its first bill (which carried it, OQ-530) due
    09/20 and unpaid: the opening money is the older debt and wins."""
    as_of = date(2026, 10, 17)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AGE-OPEN")
        _opening(account, cutover=date(2026, 8, 31), ob_90_plus="121.00")
        _bill(brazos, account, number="BL-OPEN", total="200.00", due=date(2026, 9, 20))
        segment, days = selectors.ageing_segments_for([account.id], as_of=as_of)[str(account.id)]
        # floor 91 + 47 days since cutover = 138.
        assert (segment, days) == (D90_PLUS, 138)
        assert selectors._ageing_for([account.id], as_of)[str(account.id)][2] == "opening_buckets"


def test_once_the_first_bill_is_paid_the_opening_money_stops_ageing(brazos, dana):
    """The judgment written down in `ageing_anchor_expressions`: buckets never
    shrink, so once the bill that carried them is paid they must not keep an
    account in 90+ over a 10-day-old second bill."""
    as_of = date(2026, 10, 17)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AGE-OPEN2")
        _opening(account, cutover=date(2026, 8, 31), ob_90_plus="121.00")
        first = _bill(brazos, account, number="BL-OPEN2-1", total="200.00", due=date(2026, 9, 20))
        _pay_in_full(brazos, account, first)
        _bill(brazos, account, number="BL-OPEN2-2", total="60.00", due=date(2026, 10, 7))
        assert selectors.ageing_segments_for([account.id], as_of=as_of)[str(account.id)] == (
            CURRENT,
            10,
        )


def test_an_unbilled_migrated_account_still_ages_on_its_buckets(brazos, dana):
    """The behaviour CR-030 W2 shipped is kept for the account that has no bill
    yet — its opening position IS its receivable."""
    as_of = date(2026, 10, 17)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="AGE-MIG")
        _opening(account, cutover=date(2026, 10, 1), ob_31_60="62.10")
        # floor 31 + 16 days since the 10/01 cutover = 47.
        assert selectors.ageing_segments_for([account.id], as_of=as_of)[str(account.id)] == (
            D31_60,
            47,
        )


@pytest.mark.parametrize("days", [0, 1, 29, 30, 31, 59, 60, 61, 89, 90, 91, 400])
def test_the_sql_band_and_the_python_band_agree_on_every_boundary(days):
    """`ageing_band_q` is the WHERE twin of `ageing_band_for_days`; both are
    built from `AGEING_BAND_EDGES`. Exactly one segment's predicate admits an
    anchor `days` back, and it is the Python band."""
    as_of = date(2026, 10, 17)
    anchor = as_of - timedelta(days=days)
    admitted = []
    for segment in selectors.AGEING_SEGMENTS:
        q = selectors.ageing_band_q(segment, as_of)
        lookups = {key: value for key, value in q.children if not key.endswith("__isnull")}
        ok = all(
            (anchor >= value) if key.endswith("__gte") else (anchor < value)
            for key, value in lookups.items()
        )
        if ok:
            admitted.append(segment)
    assert admitted == [selectors.ageing_band_for_days(days)]


def test_the_filter_returns_a_bill_only_account_and_only_its_band(brazos, dana):
    """`f.ageing=d61_90` — the filter the PO asked to work for bill-only
    accounts. In SQL: `account_list_is_sql_pageable` is True for it now."""
    today = _today(brazos)
    with tenant_ctx(brazos):
        late = an_account(dana, brazos, account_no="AGE-F61")
        _bill(brazos, late, number="BL-F61", total="50.00", due=today - timedelta(days=77))
        fresh = an_account(dana, brazos, account_no="AGE-F10")
        _bill(brazos, fresh, number="BL-F10", total="50.00", due=today - timedelta(days=10))
        an_account(dana, brazos, account_no="AGE-FNONE")
    from core.pagination import ListParams

    assert selectors.account_list_is_sql_pageable(ListParams(filters={"ageing": "d61_90"}))
    payload = _list(brazos, **{"f.ageing": "d61_90"})
    assert _ids(payload) == [str(late.id)]
    assert payload["results"][0]["ageing_segment"] == D61_90
    assert payload["results"][0]["ageing_days_past_due"] == 77
    assert _ids(_list(brazos, ageing="current")) == [str(fresh.id)]


def test_the_ageing_sort_puts_the_oldest_debt_first_and_nothing_owed_last(brazos, dana):
    today = _today(brazos)
    with tenant_ctx(brazos):
        a = an_account(dana, brazos, account_no="AGE-S1")
        _bill(brazos, a, number="BL-S1", total="5.00", due=today - timedelta(days=5))
        b = an_account(dana, brazos, account_no="AGE-S2")
        _bill(brazos, b, number="BL-S2", total="5.00", due=today - timedelta(days=95))
        none = an_account(dana, brazos, account_no="AGE-S3")
    desc = _ids(_list(brazos, sort="ageing", dir="desc"))
    asc = _ids(_list(brazos, sort="ageing", dir="asc"))
    assert desc == [str(b.id), str(a.id), str(none.id)]
    assert asc == [str(a.id), str(b.id), str(none.id)]


def test_another_tenants_debt_never_reaches_this_list(brazos, lonestar, dana, marcus):
    """CLAUDE.md rule 1 — the debtor read and the buckets are tenant-filtered
    on every leg, so a lonestar bill cannot age, filter or sort a brazos row."""
    today = _today(brazos)
    with tenant_ctx(lonestar):
        # No unit: lonestar enables no electric service in this fixture, and an
        # account anchored on a PREMISES with no unit is lawful since
        # customers/0036 (`ck_accounts_anchored` wants one of the two).
        from tests.test_us_met_helpers import make_premises

        premises = make_premises(marcus, address_line="9 Lone Star Way", services_available=[])
        statuses = customers_models.AccountStatus.objects.filter(tenant=lonestar)
        theirs = customers_models.Account.objects.create(
            tenant=lonestar,
            premises_id=premises["id"],
            kind="master",  # `ck_accounts_regular_has_unit`: only a master needs no unit
            status=statuses.filter(code="active").first() or statuses.first(),
            account_type=customers_models.AccountType.objects.first(),
            account_no="AGE-LS",
        )
        _bill(lonestar, theirs, number="BL-LS", total="90.00", due=today - timedelta(days=77))
    with tenant_ctx(brazos):
        mine = an_account(dana, brazos, account_no="AGE-BR")
        assert selectors.ageing_segments_for([theirs.id, mine.id]) == {}
    assert _ids(_list(brazos, **{"f.ageing": "d61_90"})) == []
    assert str(theirs.id) not in _ids(_list(brazos, sort="ageing", dir="desc"))


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10180 · ACCOUNT AGE
# ═══════════════════════════════════════════════════════════════════════════
def _opened(tenant, actor, account_no, *, opened, closed=None, status=None):
    account = an_account(actor, tenant, account_no=account_no)
    account.opened_at = opened
    account.closed_at = closed
    if status is not None:
        account.status = customers_models.AccountStatus.objects.get(tenant=tenant, code=status)
    account.save()
    return account


def test_the_row_serves_opened_and_closed(brazos, dana):
    with tenant_ctx(brazos):
        closed = _opened(brazos, dana, "AGE-C", opened=date(2019, 3, 14), closed=date(2026, 6, 30))
        pending = _opened(brazos, dana, "AGE-P", opened=None, status="pending_activation")
    rows = {row["id"]: row for row in _list(brazos)["results"]}
    assert rows[str(closed.id)]["opened_at"] == "2019-03-14"
    assert rows[str(closed.id)]["closed_at"] == "2026-06-30"
    assert rows[str(pending.id)]["opened_at"] is None
    assert rows[str(pending.id)]["closed_at"] is None


def test_account_age_sorts_oldest_first_ascending_and_pending_last_both_ways(brazos, dana):
    """PO: *"sortable oldest ↔ newest by Opened"*. 2012 (imported) · 2019 ·
    06/02/2026 · pending (no Opened) — pending is last whichever way."""
    with tenant_ctx(brazos):
        newest = _opened(brazos, dana, "AGE-N", opened=date(2026, 6, 2))
        imported = _opened(brazos, dana, "AGE-I", opened=date(2012, 3, 1))
        pending = _opened(brazos, dana, "AGE-PP", opened=None, status="pending_activation")
        middle = _opened(brazos, dana, "AGE-M", opened=date(2019, 3, 14))
    asc = _ids(_list(brazos, sort="account_age", dir="asc"))
    desc = _ids(_list(brazos, sort="account_age", dir="desc"))
    assert asc == [str(imported.id), str(middle.id), str(newest.id), str(pending.id)]
    assert desc == [str(newest.id), str(middle.id), str(imported.id), str(pending.id)]
    assert "account_age" in selectors.ACCOUNT_SQL_SORTS


def test_a_pending_account_with_a_move_in_date_still_sorts_last_and_is_not_aged(brazos, dana):
    """Rule 5 keys off the STATE: a pending account may carry the date it will
    open on, and it is still "Not opened" — last both ways, blank in the file."""
    from apps.customers import exports, services

    assert selectors.ACCOUNT_AGE_NOT_OPENED_STATUS == services.PENDING_STATUS_CODE
    with tenant_ctx(brazos):
        old = _opened(brazos, dana, "AGE-Q1", opened=date(2015, 1, 1))
        waiting = _opened(
            brazos, dana, "AGE-Q2", opened=date(2010, 1, 1), status="pending_activation"
        )
    assert _ids(_list(brazos, sort="account_age", dir="asc")) == [str(old.id), str(waiting.id)]
    assert _ids(_list(brazos, sort="account_age", dir="desc")) == [str(old.id), str(waiting.id)]
    row = {"status": "pending_activation", "opened_at": "2010-01-01", "closed_at": None}
    assert exports.account_age_duration(row, date(2026, 10, 17)) is None


def test_account_age_ties_break_on_id_so_a_page_boundary_is_stable(brazos, dana):
    with tenant_ctx(brazos):
        a = _opened(brazos, dana, "AGE-T1", opened=date(2020, 1, 1))
        b = _opened(brazos, dana, "AGE-T2", opened=date(2020, 1, 1))
    first, second = sorted([str(a.id), str(b.id)])
    assert _ids(_list(brazos, sort="account_age", dir="asc")) == [first, second]
    assert _ids(_list(brazos, sort="account_age", dir="desc")) == [second, first]


def test_a_reopened_account_restarts_its_age_from_the_reopen_date():
    """PO rule 6: *"Reopened account → age restarts from the reopen date"*. The
    list ages from `opened_at` and the CR-181 reopen WRITES `opened_at` = the
    move-in date (`REOPEN_COLUMNS`); `test_cr181_returning_customer_reopen::
    test_carry_reopens_the_same_account_and_leaves_the_balance_on_it` asserts
    the row afterwards. If the reopen ever stops writing it, this goes red and
    the list would silently age a returning customer from their first tenancy."""
    assert "opened_at" in move_in_reopen.REOPEN_COLUMNS


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10180 · THE IMPORTED OPENED DATE
# ═══════════════════════════════════════════════════════════════════════════
def test_the_import_refuses_a_future_opened_date_and_takes_an_old_one(brazos, dana):
    """PO rule 7: *"Imported account → the Opened date carried from the old
    system (optional import column; future/unreadable refused per row)"* —
    2012 → 14 yrs 7 mos. ISO and the tenant's own MM/DD/YYYY both read."""
    from apps.metering import import_runs, import_rules

    from tests.test_cr047_per_record_load import CUTOVER, HEADERS, _rows, _run, _units

    codes = {rule.code: rule for rule in import_rules.ACCOUNTS_RULES}
    rule = codes["ACC.OPENED_NOT_FUTURE"]
    assert rule.blocks and rule.rule_kind in import_rules.EVALUATORS
    future = (_today(brazos) + timedelta(days=30)).isoformat()
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=4)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-OPN1,Harmon,CUST-1,residential,active,2012-03-01,0.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-OPN2,Alvarez,CUST-2,residential,active,03/01/2012,0.00,person,123-45-6789\n"
            f"{units[2]['unit_no']},A-OPN3,Okafor,CUST-3,residential,active,{future},0.00,person,123-45-6789\n"
            f"{units[3]['unit_no']},A-OPN4,Nguyen,CUST-4,residential,active,soon,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        rows = _rows(run_id)
        assert rows[1].outcome == "staged"
        assert rows[2].outcome == "staged", rows[2].problem
        assert rows[3].outcome == "rejected"
        assert "in the future" in rows[3].problem
        assert rows[4].outcome == "rejected"
        assert "in the future" not in (rows[4].problem or "")
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        opened = dict(
            customers_models.Account.objects.filter(
                account_no__in=["A-OPN1", "A-OPN2"]
            ).values_list("account_no", "opened_at")
        )
    assert opened == {"A-OPN1": date(2012, 3, 1), "A-OPN2": date(2012, 3, 1)}


# ═══════════════════════════════════════════════════════════════════════════
# THE DOWNLOAD — Opened, Account age, Aging
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("opened", "closed", "expected"),
    [
        # The PO's own worked figures, against 10/17/2026.
        (date(2019, 3, 14), None, "P7Y7M"),
        (date(2026, 6, 2), None, "P4M"),
        (date(2026, 10, 5), None, "P12D"),
        (date(2026, 10, 14), None, "P3D"),  # reopened 10/14 → 3 days
        (date(2012, 3, 1), None, "P14Y7M"),  # imported from the old system
        # A closed account stops ageing at its Closed date.
        (date(2019, 3, 14), date(2025, 3, 14), "P6Y"),
        # Pending activation — no Opened date — is blank, never zero.
        (None, None, None),
        # The day-of-month boundary: 7 months is reached ON the 14th.
        (date(2026, 3, 14), date(2026, 10, 13), "P6M"),
        (date(2026, 3, 14), date(2026, 10, 14), "P7M"),
    ],
)
def test_the_downloads_account_age_follows_the_screens_three_rules(opened, closed, expected):
    from apps.customers import exports

    row = {
        "opened_at": opened.isoformat() if opened else None,
        "closed_at": closed.isoformat() if closed else None,
    }
    assert exports.account_age_duration(row, date(2026, 10, 17)) == expected


def test_the_accounts_download_is_registered_with_the_three_ruled_columns(brazos, dana):
    from apps.customers import exports
    from apps.tenancy import exports as export_kernel
    from core.pagination import ListParams

    resource = export_kernel.export_resource("accounts")
    assert resource is exports.ACCOUNTS
    names = [column.name for column in resource.columns]
    for name in ("opened_at", "account_age", "ageing"):
        assert name in names
    today = _today(brazos)
    with tenant_ctx(brazos):
        late = _opened(brazos, dana, "AGE-X1", opened=date(2019, 3, 14))
        _bill(brazos, late, number="BL-X1", total="50.00", due=today - timedelta(days=77))
        rows = {row["id"]: row for row in exports._rows(ListParams(filters={"ageing": "61-90"}))}
    assert list(rows) == [str(late.id)]
    row = rows[str(late.id)]
    assert row["ageing_band"] == "61-90"
    assert row["opened_at"] == "2019-03-14"
    assert row["account_age"].startswith("P7Y")
