# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `accounts` dataset query (lane DS-ACCOUNTS).
#           Drawings read as IMAGES (B14 rule 42): R22 p059 · R23 p059–p060 ·
#           R26 p060 · R27 p060–p061 · R41 p068–p069 · the master-account
#           warning p071 · §7.2/§7.2.2/§7.2.4 p083–p086 · §7.5/§7.6 p087.
# Rules:    NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-CUS-055 (a
#           status carries a behaviour class; code keys off the CLASS, never
#           the tenant's label) · BR-CUS-068 (a master account is a row like
#           any other) · BR-REP-024 (never a 0 where a figure is not derivable)
#           · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is a
#           Decimal, never a float) · hard rule 4 (this path writes nothing) ·
#           hard rule 8 (an address lives on premises and is walked to)
# ───────────────────────────────────────────────────────
"""THE `accounts` DATASET — one row per ACCOUNT, and the four grains it refuses.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *"no error"* — the commonest false pass in this repository — so no
case here is satisfied by an empty answer, and the one case that asserts a
ZERO (a page past the end) sits beside a positive one **in the same fixture**,
so an empty fixture fails the positive case before the zero can pass.

⚠ **NOTHING HERE SKIPS.** A `pytest.skip` that fires when a fixture lacks
something is a false pass. Every fixture below CREATES what it needs.

⚠ **AND THE SUITE RUNS ON IN-MEMORY SQLITE** (`config/settings/test.py`
hardcodes it and ignores `DATABASE_URL`), so these cases prove the SHAPE and
the ARITHMETIC and cannot prove anything about LIMIT/OFFSET cost, the query
plan or RLS. That is hard-won law 14; the PostgreSQL half is
`10-scripts/ds_accounts_audit_notifications_cost.py`
and `10-scripts/rep_ds_accounts_rls_proof.py`.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import accounts_dataset as dataset
from apps.customers import models as customer_models
from apps.customers.attribute_history_models import AccountAttributeHistory
from apps.reports import datasets

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Four accounts, chosen so every assertion names a NUMBER rather than a shape:
#: two billable, one base-only (a vacation hold — a LIVE account, which is why
#: `active` is two classes and not one), one terminal, and one of the four is a
#: MASTER. Balances are picked so no two subsets share a sum.
ACCOUNTS = 4
ACTIVE = 3  # billable + billable_base_only
CLOSED = 1
MASTERS = 1
WITH_BALANCE = 3
BALANCE_TOTAL = Decimal("2562.32")  # 184.52 + 2418.90 + -41.10


def _behaviour(tenant, code, name, behavior_class):
    return customer_models.AccountStatus.objects.create(
        tenant=tenant, code=code, name=name, behavior_class=behavior_class
    )


def _four(tenant, actor):
    """Four accounts on one utility, each with a stated behaviour class.

    ⚠ **THE STATUS NAMES ARE DELIBERATELY NOT THE ENGLISH ONES THE DRAWING
    SHOWS.** B14 rule 35 says a catalogue is written in its own language, and
    Phase 5's lesson is *code that was correct while every row was ours*. If a
    tile ever gets written as `status__name == "Active"`, these fixtures make it
    return 0 and the case goes red naming the count.
    """
    live = _behaviour(tenant, "OUVERT", "Ouvert", dataset.BEHAVIOUR_BILLABLE)
    hold = _behaviour(tenant, "PAUSE", "En pause", dataset.BEHAVIOUR_BILLABLE_BASE_ONLY)
    gone = _behaviour(tenant, "SOLDE", "Soldé", dataset.BEHAVIOUR_TERMINAL)

    made = []
    for index, (number, status, balance, kind, opened, closed) in enumerate(
        (
            ("100244", live, Decimal("184.52"), "regular", date(2024, 3, 12), None),
            ("100512", live, Decimal("2418.90"), "regular", date(2023, 4, 1), None),
            ("100733", hold, Decimal("0"), dataset.KIND_MASTER, date(2025, 1, 5), None),
            ("100907", gone, Decimal("-41.10"), "regular", date(2022, 6, 1), date(2025, 8, 22)),
        )
    ):
        account = an_account(tenant, actor, account_no=number, label=f"Unit {index}")
        account.status = status
        account.balance = balance
        account.kind = kind
        account.opened_at = opened
        account.closed_at = closed
        account.save()
        made.append(account)
    return made


# ══════════════════════════════════════════════════════════════════════════
#  R22 — the one it serves
# ══════════════════════════════════════════════════════════════════════════


def test_r22_serves_one_row_per_account_and_the_tiles_foot(brazos, dana):
    """R22's four tiles are a SQL aggregate over the whole filtered set.

    ⚠ **FALSE PASS THIS GUARDS:** if `totals` were struck over the PAGE, a
    `per=2` request would report `accounts: 2` and the tile would foot to the
    page instead of to the book. The case asks for a page of TWO out of FOUR
    and asserts the tile still says four.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        result = dataset.accounts_dataset(per=2, page=1)

    assert result["grain"] == "one account"
    assert len(result["rows"]) == 2  # the page
    assert result["total"] == ACCOUNTS  # the book
    assert result["pages"] == 2
    totals = result["totals"]
    assert totals["accounts"] == ACCOUNTS
    assert totals["active"] == ACTIVE
    assert totals["closed"] == CLOSED
    assert totals["with_balance"] == WITH_BALANCE
    assert totals["balance"] == BALANCE_TOTAL
    assert isinstance(totals["balance"], Decimal)  # hard rule 2 — never a float


def test_the_tiles_key_off_the_behaviour_class_not_the_status_label(brazos, dana):
    """BR-CUS-055 and Phase 5's lesson, in one case.

    ⚠ **THE FALSE PASS:** a tile written `status__name="Active"` passes on the
    seeded demo tenant and returns **0** for a utility whose statuses are in its
    own language. Every status name in this fixture is French, so a label-keyed
    tile reports zero active accounts over three live ones and this case is what
    goes red.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        result = dataset.accounts_dataset()

    names = {row.status for row in result["rows"]}
    assert names == {"Ouvert", "En pause", "Soldé"}
    assert result["totals"]["active"] == ACTIVE
    assert result["totals"]["active"] > 0
    # The base-only hold IS active: two classes, not one.
    behaviours = {row.status_behaviour for row in result["rows"] if row.status == "En pause"}
    assert behaviours == {dataset.BEHAVIOUR_BILLABLE_BASE_ONLY}


def test_a_master_account_is_a_row_like_any_other_marked_never_merged(brazos, dana):
    """p071 / BR-CUS-068. It is COUNTED, it is MARKED, and nothing merges it."""
    with tenant_ctx(brazos):
        _four(brazos, dana)
        result = dataset.accounts_dataset()

    kinds = [row.kind for row in result["rows"]]
    assert kinds.count(dataset.KIND_MASTER) == MASTERS
    # Counted in the census, not excluded from it.
    assert result["totals"]["accounts"] == ACCOUNTS
    # And reported separately so a renderer can MARK it.
    assert result["totals"]["master_accounts"] == MASTERS


def test_as_of_is_a_membership_window_and_says_its_attributes_are_as_is(brazos, dana):
    """§7.2.4 — membership is answerable, class/type/status are not.

    The four open on 2024-03-12, 2023-04-01, 2025-01-05 and 2022-06-01, and one
    of them shut on 2025-08-22. So a census as at **1 Feb 2025** holds FOUR and
    one as at **1 Jan 2026** holds THREE. Both are non-zero.

    ⚠ **A THIRD DATE IS ASSERTED ON PURPOSE.** As at **1 Dec 2024** only THREE
    had opened, because the master opens on 2025-01-05. A membership window that
    honoured `closed_at` and ignored `opened_at` would pass the first two
    assertions and fail this one, and that is precisely the half-implemented
    version a reader would not notice.

    ⚠ **THE FALSE PASS:** a query that ignored `as_of` entirely returns four
    every time and nothing looks wrong, so the case asserts ALL THREE numbers.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        not_all_open_yet = dataset.accounts_dataset(as_of=date(2024, 12, 1))
        before = dataset.accounts_dataset(as_of=date(2025, 2, 1))
        after = dataset.accounts_dataset(as_of=date(2026, 1, 1))

    assert not_all_open_yet["total"] == 3
    assert before["total"] == 4
    assert after["total"] == 3
    # Every row here predates the attribute-history table, so every one falls
    # back to as-is — marked per row, and COUNTED rather than hand-waved.
    assert all(row.attribute_basis == "as_is" for row in after["rows"])
    fallback = [
        problem
        for problem in after["problems"]
        if problem["code"] == "some_rows_have_no_history_period_and_fell_back_to_as_is"
    ]
    assert len(fallback) == 1
    assert "3 of the 3 rows served" in fallback[0]["detail"]


def test_as_was_wins_where_a_history_period_covers_the_date(brazos, dana):
    """§7.2.4 option (b), RULED **and BUILT** (`P0.18`) — and the brief is stale.

    ⚠ **THE BRIEF SAYS THIS IS IMPOSSIBLE AND THE CODE SAYS IT IS NOT.** §7.2.4
    (p085) states as a measurement that *"apps/customers/models.py has no
    effective dating of any kind"*. That was true when it was written;
    `customers/0072_cr142_p0_18_attribute_history` shipped on 2026-09-26 and the
    columns live in `attribute_history_models.py`. **A dataset built from the
    brief's sentence would have reported today's class on every historical
    census, with a caveat explaining why that was unavoidable** — a plausible
    number under an excuse, which is the worst of both.

    ⚠ **THE FALSE PASS:** reading `account.status` regardless passes every other
    case in this file. Here the account is Commercial TODAY and was Residential
    in June, and the June census must say Residential.

    ⚠ **AND THE TILE MUST FOOT TO THE ROWS.** The account is terminal today and
    was billable in June, so June's ACTIVE tile counts it and today's does not.
    A tile left reading today's column would disagree with the row beneath it.
    """
    with tenant_ctx(brazos):
        made = _four(brazos, dana)
        account = made[0]
        residential = customer_models.AccountType.objects.create(
            tenant=brazos, code="RES", name="Résidentiel"
        )
        commercial = customer_models.AccountType.objects.create(
            tenant=brazos, code="COM", name="Commercial"
        )
        was_live = customer_models.AccountStatus.objects.get(tenant=brazos, code="OUVERT")
        now_gone = customer_models.AccountStatus.objects.get(tenant=brazos, code="SOLDE")
        # The closed period: Residential and live, 1 Jan → 1 Sep 2026.
        AccountAttributeHistory.objects.create(
            tenant=brazos,
            account=account,
            account_type=residential,
            status=was_live,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 9, 1),
        )
        # The open period: Commercial and closed, from 1 Sep 2026.
        AccountAttributeHistory.objects.create(
            tenant=brazos,
            account=account,
            account_type=commercial,
            status=now_gone,
            effective_from=date(2026, 9, 1),
            effective_to=None,
        )
        account.account_type = commercial
        account.status = now_gone
        account.save()

        june = dataset.accounts_dataset(as_of=date(2026, 6, 30), sort="account_no")
        today = dataset.accounts_dataset(as_of=date(2026, 9, 30), sort="account_no")

    june_row = [row for row in june["rows"] if row.account_no == "100244"][0]
    today_row = [row for row in today["rows"] if row.account_no == "100244"][0]
    assert june_row.attribute_basis == "as_was"
    assert june_row.account_class == "Résidentiel"
    assert june_row.status == "Ouvert"
    assert today_row.attribute_basis == "as_was"
    assert today_row.account_class == "Commercial"
    assert today_row.status == "Soldé"

    # The tile reads the same basis the rows do — a non-zero on both sides.
    # ⚠ Both dates hold THREE accounts, not four: 100907 shut on 22 Aug 2025 and
    # is not a member on either. So `closed` here is the ONE account whose
    # as-was status is terminal on the date — the membership window and the
    # status tile are two different questions and both are answered.
    assert june["total"] == 3
    assert today["total"] == 3
    assert june["totals"]["active"] == 3
    assert june["totals"]["closed"] == 0
    assert today["totals"]["active"] == 2
    assert today["totals"]["closed"] == 1


def test_a_class_filter_on_an_as_at_read_matches_what_the_row_shows(brazos, dana):
    """A filter must match the displayed value, or the chip lies.

    ⚠ **THE FALSE PASS:** filtering on `accounts.account_type_id` (today's
    column) returns the row under a *Résidentiel* chip while the row itself
    says *Commercial*. Both directions are asserted, and both are non-zero.
    """
    with tenant_ctx(brazos):
        made = _four(brazos, dana)
        account = made[0]
        residential = customer_models.AccountType.objects.create(
            tenant=brazos, code="RES", name="Résidentiel"
        )
        commercial = customer_models.AccountType.objects.create(
            tenant=brazos, code="COM", name="Commercial"
        )
        live = customer_models.AccountStatus.objects.get(tenant=brazos, code="OUVERT")
        AccountAttributeHistory.objects.create(
            tenant=brazos,
            account=account,
            account_type=residential,
            status=live,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 9, 1),
        )
        account.account_type = commercial
        account.save()

        as_residential = dataset.accounts_dataset(
            as_of=date(2026, 6, 30), account_class=residential.id
        )
        as_commercial = dataset.accounts_dataset(
            as_of=date(2026, 6, 30), account_class=commercial.id
        )

    assert as_residential["total"] == 1  # the as-was value, which is what shows
    assert [row.account_class for row in as_residential["rows"]] == ["Résidentiel"]
    assert as_commercial["total"] == 0  # today's value does NOT match the chip


def test_the_address_is_walked_to_premises_and_no_column_holds_one(brazos, dana):
    """Hard rule 8 — the drawn warning on p059, asserted rather than described.

    ⚠ **THE FALSE PASS THIS GUARDS IS `DEF-CUS-3653`'s:** composing the line
    from `customers.addresses` `kind='service'` — a retired value with zero rows
    — returns `None` on every account forever with `tsc` and every test green.
    So the case asserts a NON-EMPTY street on every row, which a retired-kind
    read cannot produce.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        result = dataset.accounts_dataset()

    assert len(result["rows"]) == ACCOUNTS
    assert all(row.premises_line1 for row in result["rows"])
    assert all(row.unit_label for row in result["rows"])
    # And the row type declares no address of its own beyond the walked fields.
    assert not hasattr(result["rows"][0], "city")
    assert not hasattr(result["rows"][0], "address_line")


def test_the_page_is_cut_in_sql_and_the_last_page_is_not_empty(brazos, dana):
    """NFR-3 — `limit`/`offset` in SQL, never a Python slice of everything.

    ⚠ **THE FALSE PASS:** a page past the end returning `[]` reads as *no
    error*. It sits here beside `page=2`, which must hold TWO rows, so an empty
    fixture fails the positive assertion first.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        second = dataset.accounts_dataset(per=2, page=2, sort="account_no", direction="asc")
        beyond = dataset.accounts_dataset(per=2, page=9)

    assert [row.account_no for row in second["rows"]] == ["100733", "100907"]
    # Clamped to the last page rather than serving an empty one.
    assert beyond["page"] == 2
    assert len(beyond["rows"]) == 2
    query = str(
        dataset._ordered(
            customer_models.Account.objects.all(), "account_no", "asc"
        ).query
    )
    assert "ORDER BY" in query.upper()


def test_every_sort_ends_in_a_unique_column(brazos):
    """A page is a window over an ORDER; a partial order loses and repeats rows."""
    for name, terms in dataset.ACCOUNT_SORT_COLUMNS.items():
        assert terms[-1] == "id", f"{name} has no unique tiebreak"
    assert set(dataset.ACCOUNT_SORTS) == set(dataset.ACCOUNT_SORT_COLUMNS)


def test_the_export_takes_no_page_and_no_per(brazos, dana):
    """§7.5 — an export cannot inherit a screen's fifty rows because there is
    no argument through which to pass them."""
    import inspect

    signature = inspect.signature(dataset.accounts_dataset_stream)
    assert "page" not in signature.parameters
    assert "per" not in signature.parameters

    with tenant_ctx(brazos):
        _four(brazos, dana)
        streamed = list(dataset.accounts_dataset_stream(sort="account_no", direction="asc"))
    assert len(streamed) == ACCOUNTS
    assert [row.account_no for row in streamed][0] == "100244"


def test_the_route_filter_is_refused_rather_than_ignored(brazos, dana):
    """A filter the dataset declares and the query drops shows the WHOLE set
    under a chip that says otherwise — hard-won law 2's mirror."""
    with tenant_ctx(brazos):
        _four(brazos, dana)
        with pytest.raises(dataset.UnservableFromThisDataset) as raised:
            dataset.accounts_dataset(route="R-03")
    assert "route" in str(raised.value)


def test_no_measure_here_claims_to_be_fully_additive(brazos, dana):
    """§7.2.2 — `accounts` and `balance` sum across accounts, never across time.

    The footer refusal reads this declaration, so a dataset that claimed a
    fully-additive measure would turn the em-dash back into a wrong total.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        result = dataset.accounts_dataset()

    codes = {problem["code"] for problem in result["problems"]}
    assert dataset.GAP_NO_FULLY_ADDITIVE_MEASURE["code"] in codes
    declared = {measure.name: measure.additivity for measure in datasets.ACCOUNTS.measures}
    assert declared["accounts"] == datasets.ADD_SEMI
    assert declared["balance"] == datasets.ADD_SEMI


def test_a_share_of_nothing_is_none_and_never_zero(brazos, dana):
    """BR-REP-024 — 0% on an empty report reads as a real measurement.

    ⚠ The zero case sits in the SAME test as a positive one, so an empty
    fixture cannot satisfy it.
    """
    with tenant_ctx(brazos):
        _four(brazos, dana)
        populated = dataset.accounts_dataset()
        empty = dataset.accounts_dataset(as_of=date(2000, 1, 1))

    assert populated["totals"]["with_balance_pct"] == Decimal(3) / Decimal(4) * Decimal(100)
    assert empty["total"] == 0
    assert empty["totals"]["with_balance_pct"] is None


# ══════════════════════════════════════════════════════════════════════════
#  THE FOUR IT REFUSES
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "code,report",
    [
        ("account_activity", "R23"),
        ("data_quality", "R26"),
        ("plans_and_discounts", "R27"),
        ("migration_assurance", "R41"),
    ],
)
def test_each_refusal_names_the_report_the_grain_and_the_read_model(code, report):
    """A refusal is DATA, not a comment (hard-won law 1).

    ⚠ **IT RAISES RATHER THAN RETURNING `[]`.** An empty result reads as *no
    rows matched*, which a clerk will act on; only a refusal naming the report
    and the grain is output a READER can tell apart from a working report.
    """
    row = dataset.unservable_reason(code)
    assert row["report"].startswith(report)
    assert row["drawn_grain"] and row["drawn_grain"] != "one account"
    assert row["needs_read_model"]
    assert row["evidence"]
    assert row["warning_obeyed"]

    with pytest.raises(dataset.UnservableFromThisDataset) as raised:
        dataset.refuse(code)
    message = str(raised.value)
    assert report in message
    assert "one account" in message


def test_the_refusals_cover_every_seeded_report_but_r22():
    """The four seeded onto `accounts` that are not R22 are each refused BY NAME.

    ⚠ **THE FALSE PASS THIS GUARDS:** a lane deleting a refusal row would leave
    a report resolving to a query that answers a different question, which is
    invisible to every gate and to the clerk. Counted, not glanced at.
    """
    assert set(dataset.UNSERVABLE_HERE) == {
        "account_activity",
        "data_quality",
        "plans_and_discounts",
        "migration_assurance",
    }
    assert len(dataset.UNSERVABLE_HERE) == 4


def test_this_module_writes_nothing(brazos, dana):
    """Hard rule 4 — a report is a READ. Asserted against the source text,
    because a docstring claiming a guarantee is not the guarantee (law 1)."""
    import inspect

    source = inspect.getsource(dataset)
    for forbidden in (".save(", ".create(", ".delete(", ".update(", "bulk_create"):
        assert forbidden not in source, f"{forbidden} is a write and this path is a read"
