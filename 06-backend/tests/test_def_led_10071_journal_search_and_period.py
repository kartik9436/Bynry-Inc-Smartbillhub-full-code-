# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-LED-10071 (the Journal search finds only the entry number and
#           the memo; the period cannot be chosen) · DEF-LED-10072 (the Trial
#           balance period is plain text — this file proves the SERVER half:
#           opening before From, movement inside, closing at To) ·
#           DEF-LED-10073 (a drawer-difference memo written at 4 decimals)
# Ruling:   12-governance/02-decision-log.md 2026-10-12 · "FINANCE: JOURNAL
#           SEARCH AND THE PERIOD CONTROLS" — J1 PO verbatim: *"J1 - this is
#           good add cutomer name to search"*; CONFIRMED *"this good please
#           start and fix it"*
# Rules:    BR-LED-012 (the journal list) · BR-TEN-013 (no module reads another
#           module's ORM — the search asks each owner's published read) ·
#           NFR-3 (one SQL query, still paged) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 2 (money stored 4dp, DISPLAY 2) · hard rule 4
#           (a posted memo is never rewritten)
# ───────────────────────────────────────────────────────
"""J1 · J6 · P3 · fault A, proved against the ledger read models.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ANSWERED ONE BY ONE (law 7 (2)).**

* *A search leg that matches EVERYTHING* — every case asserts the unrelated
  entry is ABSENT, not merely that the wanted one is present.
* *A search that returns the entry once per matching line* — the Larkspur
  entry carries the dimension on TWO lines, and the count must be one.
* *A row totalled over the matching lines only* — the dimension sits on the
  debit line alone in the Quarry entry, so a narrowed total would read 100.00
  debit and 0.00 credit. The row must read 100.00 / 100.00, balanced.
* *A trial balance whose closing is merely the window's movement* — the June
  entry sits BEFORE From, so opening is non-zero and closing ≠ movement.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.ledger import models as ledger_models
from apps.ledger import posting, reporting
from apps.payments.ledger_seam import drawer_difference_memo

from tests.ledger_le_fixtures import a_request, gl, line
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

D = Decimal


def _cast(tenant, actor):
    """Two homes, two accounts, two customers — nothing shared between them."""
    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account_type = customer_models.AccountType.objects.first()
    cast = {}
    for key, address, label, account_no, customer_no, name in (
        ("larkspur", "812 Larkspur Ln", "Unit 9C", "A-77001", "C-50001", "Marisol Vega"),
        ("quarry", "47 Quarry Rd", "Unit 2A", "A-88002", "C-60002", "Teodoro Banks"),
    ):
        premises = make_premises(actor, address_line=address, services_available=["electric"])
        unit = make_unit(actor, premises["id"], label=label, services=["electric"])
        account = customer_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            account_no=account_no,
            status=status,
            account_type=account_type,
        )
        customer = customer_models.Customer.objects.create(
            tenant=tenant, customer_no=customer_no, display_name=name
        )
        cast[key] = {
            "account_id": account.pk,
            "premises_id": premises["id"],
            "unit_id": unit["id"],
            "customer_id": customer.pk,
        }
    return cast


def _post(tenant, key, entry_date, lines, memo="fixture"):
    return posting.post(a_request(lines, key=key, entry_date=entry_date, memo=memo))


def _book(tenant, cast):
    """Three entries, each balanced, each with its dimensions on SOME lines."""
    ar = gl(tenant, "1200", "asset")
    revenue = gl(tenant, "4100", "revenue")
    tax = gl(tenant, "2200-03", "liability", name="Tax payable")
    L = cast["larkspur"]
    Q = cast["quarry"]
    # Larkspur: the dimension on TWO lines (AR and revenue), the tax line bare.
    _post(
        tenant,
        "j1-larkspur",
        date(2026, 7, 10),
        [
            line(ar, ledger_models.SIDE_DEBIT, "100.00", **L),
            line(revenue, ledger_models.SIDE_CREDIT, "90.00", **L),
            line(tax, ledger_models.SIDE_CREDIT, "10.00"),
        ],
    )
    # Quarry: the dimension on the DEBIT line only.
    _post(
        tenant,
        "j1-quarry",
        date(2026, 7, 20),
        [
            line(ar, ledger_models.SIDE_DEBIT, "100.00", **Q),
            line(revenue, ledger_models.SIDE_CREDIT, "100.00"),
        ],
    )
    # June — before the window, the opening position for P3.
    _post(
        tenant,
        "j1-june",
        date(2026, 6, 15),
        [
            line(ar, ledger_models.SIDE_DEBIT, "40.00", **Q),
            line(revenue, ledger_models.SIDE_CREDIT, "40.00"),
        ],
    )
    return {"ar": ar, "revenue": revenue}


def _numbers(result):
    return sorted(row.memo + "@" + row.entry_date.isoformat() for row in result["rows"])


# ═══════════════════════════════════════════════════════════════════════════
# J1 — the search finds an entry by what its LINES belong to
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "term, why",
    [
        ("A-77001", "account number"),
        ("77001", "part of the account number"),
        ("C-50001", "customer number"),
        ("Marisol Vega", "customer name"),
        ("vega", "any part of the customer name, any case"),
        ("Larkspur", "premises address"),
        ("9C", "unit label"),
    ],
)
def test_j1_each_dimension_finds_the_entry_and_nothing_unrelated(brazos, dana, term, why):
    with tenant_ctx(brazos):
        cast = _cast(brazos, dana)
        _book(brazos, cast)
        result = reporting.journal_entry_list(search=term)
        dates = [row.entry_date for row in result["rows"]]
        assert dates == [date(2026, 7, 10)], f"{why}: {term!r} found {dates}"
        assert result["total"] == 1


def test_j1_the_whole_entry_is_returned_and_it_still_balances(brazos, dana):
    """Totals are over ALL of an entry's lines, never the matching ones."""
    with tenant_ctx(brazos):
        cast = _cast(brazos, dana)
        _book(brazos, cast)
        (larkspur,) = reporting.journal_entry_list(search="Larkspur")["rows"]
        assert (larkspur.debit, larkspur.credit, larkspur.balanced) == (D("100"), D("100"), True)
        # The dimension sits on the debit line ONLY here; a narrowed total
        # would read 100 / 0 and flag a balanced entry as broken.
        rows = reporting.journal_entry_list(search="Quarry", start=date(2026, 7, 1))["rows"]
        assert [(r.debit, r.credit, r.balanced) for r in rows] == [(D("100"), D("100"), True)]


def test_j1_the_old_legs_still_work_and_the_search_stays_paged(brazos, dana):
    with tenant_ctx(brazos):
        cast = _cast(brazos, dana)
        ar = gl(brazos, "1200", "asset")
        revenue = gl(brazos, "4100", "revenue")
        for n in range(3):
            _post(
                brazos,
                f"j1-page-{n}",
                date(2026, 7, 1 + n),
                [
                    line(ar, ledger_models.SIDE_DEBIT, "5.00", **cast["larkspur"]),
                    line(revenue, ledger_models.SIDE_CREDIT, "5.00", **cast["larkspur"]),
                ],
                memo=f"page {n}",
            )
        # memo leg unchanged
        assert reporting.journal_entry_list(search="page 1")["total"] == 1
        # dimension leg, paged in SQL: total over the set, rows a page
        page = reporting.journal_entry_list(search="Larkspur", offset=0, limit=2)
        assert page["total"] == 3
        assert len(page["rows"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# J3 / J6 — the from/to window narrows in SQL
# ═══════════════════════════════════════════════════════════════════════════
def test_j3_the_window_is_inclusive_at_both_ends(brazos, dana):
    with tenant_ctx(brazos):
        cast = _cast(brazos, dana)
        _book(brazos, cast)
        july = reporting.journal_entry_list(start=date(2026, 7, 10), end=date(2026, 7, 20))
        assert sorted(r.entry_date for r in july["rows"]) == [date(2026, 7, 10), date(2026, 7, 20)]
        assert reporting.journal_entry_list(start=date(2026, 7, 11), end=date(2026, 7, 19))["total"] == 0
        # No window at all (J4) — every entry.
        assert reporting.journal_entry_list()["total"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# P3 — opening before From, movement inside, closing at To
# ═══════════════════════════════════════════════════════════════════════════
def test_p3_opening_is_before_from_and_closing_is_opening_plus_movement(brazos, dana):
    with tenant_ctx(brazos):
        cast = _cast(brazos, dana)
        accounts = _book(brazos, cast)
        tb = reporting.trial_balance(start=date(2026, 7, 1), end=date(2026, 7, 31))
        ar = next(r for r in tb["rows"] if str(r["account_id"]) == str(accounts["ar"].pk))
        # June's 40.00 is the opening; July's 200.00 is the movement.
        assert ar["opening"] == D("40")
        assert ar["debit"] - ar["credit"] == D("200")
        assert ar["closing"] == D("240")
        for row in tb["rows"]:
            assert row["closing"] == row["opening"] + row["debit"] - row["credit"]
        # A window ending before the Quarry entry leaves it out of the movement.
        early = reporting.trial_balance(start=date(2026, 7, 1), end=date(2026, 7, 15))
        ar_early = next(r for r in early["rows"] if str(r["account_id"]) == str(accounts["ar"].pk))
        assert (ar_early["opening"], ar_early["closing"]) == (D("40"), D("140"))


# ═══════════════════════════════════════════════════════════════════════════
# Fault A — DEF-LED-10073: the drawer memo shows money at DISPLAY precision
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "amount, over, currency, memo",
    [
        (D("10.0000"), False, "USD", "Counter drawer short $10.00"),
        (D("12.5000"), True, "USD", "Counter drawer over $12.50"),
        (D("3.0000"), False, "CAD", "Counter drawer short $3.00"),
        (D("7.0000"), False, "EUR", "Counter drawer short EUR 7.00"),
    ],
)
def test_fault_a_the_drawer_memo_is_written_at_two_decimals(amount, over, currency, memo):
    """RED BEFORE: `Counter drawer short 10.0000` — the stored figure, verbatim."""
    assert drawer_difference_memo(amount, over=over, currency=currency) == memo
