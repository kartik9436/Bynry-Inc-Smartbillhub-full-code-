# ── Trace ──────────────────────────────────────────────
# Change:   CR-061 STATEMENT (1) (2026-09-01) — *"actually you need more GL code
#           s and categories, I tried to assigned using existing code, they are
#           not sufficiencnt"*, completed on the PO's instruction of 2026-09-02,
#           *"complete 61 based on actual code"*. Statement (2) — the discount —
#           is `test_cr061_contra_revenue_type.py` and landed 2026-09-01.
# Story:    US-LED-005 (the chart: seeded at provisioning, tenant-customizable)
#           · US-LED-017 TC-5 (no surface presents an unsigned code as signed)
#           Screens: S56 · Settings → Accounting
# Rules:    BR-LED-014 · BR-LED-015 (every chart change audits) · BR-REP-006
#           (pickers enumerate the LIVE vocabulary) · BR-BIL-069 (the 2200 tax
#           series is minted, never seeded) · CLAUDE.md hard rule 4 (posted
#           lines are append-only — nothing here rewrites one)
# Golden:   NOTHING HERE MOVES A FROZEN FIGURE and tc8 is the proof: G61's 130
#           ❄️ money figures, `03-golden-verify.py` 33/0 and G64's 14-of-61 are
#           identical before and after. A chart HEADING cannot move an amount.
# Tests:    this file
# Impacts:  apps/ledger/chart.UTILITY_BOOKS_CHART (new, 67 rows) ·
#           chart.CHART_CATEGORIES (new, 18) · chart.UTILITY_BOOKS_NOT_SEEDED
#           (the refusals, as data) · models.LedgerAccount.category (new column,
#           ledger/0013) · services._wanted_rows (58 → 125)
# ───────────────────────────────────────────────────────
"""CR-061 statement (1) — more GL codes, and headings to read them under.

WHAT THE PRODUCT OWNER RULED, AND WHY IT IS A FIELD REPORT
-----------------------------------------------------------
> *"if you need differnt number assign it - im okay with it; actually you need
> more GL code s and categories, I tried to assigned using existing code, they
> are not sufficiencnt"* — 2026-09-01

> *"complete 61 based on actual code"* — 2026-09-02

The PO sat down to assign GL codes with the chart this product ships and RAN
OUT. Nothing in this repo asked whether the chart was big enough, so nothing
would have surfaced it.

THE ONE RULE THAT DECIDES WHICH REFERENCE ROWS ARE SEEDED
----------------------------------------------------------
*A reference row is seeded when it names a place the product does not already
have. It is NOT seeded when the product already posts that fact somewhere.*
`tc4` is the second half and it is the half that matters: `1220 Customer AR –
Electric` would LOOK like the account electric receivables land in, and they
would not — every receivable posts through the ONE `accounts_receivable`
designation, which the database makes unique per tenant. **A chart row that will
always read zero while a human reconciles against it is worse than an absent
one**, which is hard-won law 2 applied to data.

WHAT IS DELIBERATELY NOT ASSERTED HERE
---------------------------------------
That an EXISTING database ends up with these 67 accounts or with any heading at
all. It does not, and cannot: `services._create_missing_accounts` skips any code
the tenant already holds and nothing backfills `category` (hard-won law 4). A
tenant provisioned before 2026-09-02 sees its whole chart under one
*Uncategorised* heading until somebody files the rows. `DEF-3060` is that gap
for a CHANGED seed row and `OQ-1280` is its finance half.
"""

from __future__ import annotations

import pytest

from apps.ledger import chart, models as ledger_models, services as ledger_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Quoted from the ruling and from the PO's own reference chart rather than read
#: back out of `chart.py` — a test that asked the code what the code says would
#: pass on any value at all.
BOOKS_ROW_COUNT = 67
#: `CR-061`'s own four tuples: 36 signed + 8 cost + 14 widened + 67 books = 125.
#: ⚠ **126 SINCE 2026-09-03: `4165 Battery`.** PO ruling that day, verbatim:
#: *"We need seperate code for Solar 4150 and Battery 4150"*. Solar and battery
#: shared 4150 because B5 line 74 names one account for the pair, so a utility
#: selling both saw one number and could not tell them apart. Battery moved to
#: its own account; solar kept 4150. **This constant is quoted from the ruling
#: and not read back out of `chart.py`** — see the note above — so it MUST be
#: moved by hand when the chart moves, and this assertion going red is that
#: rule working rather than a test to relax.
#: ⚠ **127 SINCE 2026-09-23: `6850 Cash over and short`.** PO ruling that day
#: (`CR-136-BRC07` §3.3), verbatim: *"(b) Post it. A short writes a balanced
#: pair to a cash over/short account the day it is declared. Needs one new
#: account added to the chart"* — so a counted drawer difference has somewhere
#: to land, ONE account for both directions. **This assertion went RED when
#: that row landed and this edit is the rule above working**, not a relaxation:
#: the number is moved by hand, naming exactly what joined.
TOTAL_SEEDED = 127

#: ⚠ **WHAT A FRESH TENANT ACTUALLY RECEIVES, AND IT IS ONE MORE — `DEF-3441`.**
#: `TOTAL_SEEDED` above and this are two different facts and shared one constant
#: until 2026-09-03, which is why moving the number broke the other assertion
#: rather than fixing anything: tc1 sums the four tuples `CR-061` wrote, and
#: tc5 counts the rows `services._wanted_rows` hands provisioning — and on
#: 2026-09-02 `CR-060` T7f added a FIFTH tuple to that sum,
#: `chart.PERIOD_MATCHING_CHART`, holding `5700 Depreciation expense`. The count
#: went to 126 and nobody ran this file.
#:
#: Still TYPED and not derived, for the reason the comment above gives — a test
#: that asks the code what the code says passes on any value at all — so it
#: moves by a deliberate edit naming exactly what joined.
#:
#: `1290 Allowance for doubtful accounts` is deliberately NOT among them:
#: `CR-060` T15 mints it when a tenant switches the allowance policy on, never
#: at provisioning, so a utility that never books an allowance still gets 126.
TOTAL_PROVISIONED = TOTAL_SEEDED + len(chart.PERIOD_MATCHING_CHART)
CATEGORY_COUNT = 18

#: Reference rows the PO's chart names that this product already posts
#: somewhere, keyed by their row number in `CR-061` §5. Seeding any of them
#: would be a row that always reads zero.
ALREADY_POSTED_ELSEWHERE = {
    9: "1200",
    10: "1210",
    11: "1220",
    12: "1230",
    13: "1240",
    15: "1260",
    30: "4620",
    37: "4750",
    39: "2310",
    40: "2320",
    41: "2330",
    42: "2340",
    87: "6420",
}


# ═══════════════════════════════════════════════════════════════════════════
# tc1 — THE RULING'S FIRST HALF: more GL codes, and they collide with nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc1__sixty_seven_new_codes_and_not_one_collision():
    """*"you need more GL code s"* — 67 of them, and a code is unique per tenant.

    `uq_ledger_accounts_code` makes a duplicate a database error at
    provisioning, so a collision here is a tenant that CANNOT BE CREATED. It is
    asserted across all four tuples rather than inside the new one, because the
    new one is the only one that could collide with the other three.
    """
    assert len(chart.UTILITY_BOOKS_CHART) == BOOKS_ROW_COUNT
    every = (
        chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
    )
    assert len(every) == TOTAL_SEEDED
    codes = [row.code for row in every]
    assert len(codes) == len(set(codes)), "a duplicate code makes a tenant unprovisionable"

    # BR-BIL-069 / B5 line 74 ❄️ — *"tenant authorities mint their own"*. The
    # 2200 series stays seeded to NOBODY, and the new debt block deliberately
    # starts at 2500 to leave it whole.
    assert not [code for code in codes if code.startswith(chart.TAX_PAYABLE_SERIES)]

    # The four rows that could not take the reference's own number, because the
    # number is a FINANCE-SIGNED row of B5 line 74 that no lane may move.
    by_code = {row.code: row for row in chart.UTILITY_BOOKS_CHART}
    assert by_code["1060"].name == "Restricted cash"  # reference says 1010
    assert by_code["3040"].name == "Capital grants & contributions"  # reference says 3000
    signed = {row.code: row for row in chart.SEED_CHART}
    assert signed["1010"].signed and signed["1010"].name == "Undeposited funds"
    assert signed["3000"].signed and signed["3000"].name == "Opening balance clearing"


# ═══════════════════════════════════════════════════════════════════════════
# tc2 — THE SECOND HALF: eighteen headings, and every seeded row has one
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc2__every_seeded_row_carries_one_of_the_eighteen_headings():
    """*"...and categories"*.

    A heading that no row uses is a filter value that returns nothing; a row
    with no heading is a row that falls out of a grouped screen. Both directions
    are asserted, because a chart of 125 accounts is only readable if the
    grouping is complete.
    """
    assert len(chart.CHART_CATEGORIES) == CATEGORY_COUNT
    assert len(set(chart.CHART_CATEGORIES)) == CATEGORY_COUNT

    every = (
        chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
    )
    uncategorised = [row.code for row in every if row.category is None]
    assert uncategorised == [], f"seeded rows with no heading: {uncategorised}"
    unknown = [row.code for row in every if not chart.is_chart_category(row.category)]
    assert unknown == [], f"seeded rows under a heading nothing groups by: {unknown}"

    # Every heading is used by at least one row — EXCEPT the tax series, which
    # is seeded to nobody by BR-BIL-069 and gets a heading precisely BECAUSE a
    # minted authority account would otherwise be the one row with no home.
    used = {row.category for row in every}
    assert set(chart.CHART_CATEGORIES) - used == {chart.CAT_TAXES_PAYABLE}


# ═══════════════════════════════════════════════════════════════════════════
# tc3 — THE SIGNATURE: 67 unsigned rows, and NO surface may call them signed
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc3__all_sixty_seven_are_unsigned_and_the_third_register_carries_them(brazos):
    """US-LED-017 TC-5 — *"no surface presents an unsigned code as signed"*.

    **The PO ruled the CODES into existence. That is not a finance signature**,
    no dollar figure is attached to any row, and B5 line 74 stays ❄️ FROZEN and
    un-edited. So all 67 carry `signed=False` and land in a THIRD pending
    register beside the other two.

    ⚠ **THE FAILURE THIS CASE EXISTS FOR IS THE OMISSION, NOT THE FLAG.**
    `services._chart_row` computes `finance_signed` by asking the pending
    registers, and it asked TWO of them. Adding 67 unsigned rows without adding
    the third register serves every one of them as `finance_signed: true` —
    which is exactly the defect fixed here on 2026-08-18, pointed the other way.
    """
    assert [row.code for row in chart.UTILITY_BOOKS_CHART if row.signed] == []
    assert set(chart.PENDING_FINANCE_RE_SIGN_BOOKS) == {
        row.code for row in chart.UTILITY_BOOKS_CHART
    }
    # The three registers are disjoint: one code, one register, or a reader
    # cannot tell which signature a row is waiting for.
    assert not set(chart.PENDING_FINANCE_RE_SIGN_BOOKS) & set(chart.PENDING_FINANCE_RE_SIGN)
    assert not set(chart.PENDING_FINANCE_RE_SIGN_BOOKS) & set(chart.PENDING_FINANCE_RE_SIGN_COST)

    with tenant_ctx(brazos):
        served = ledger_services.chart_of_accounts()
    rows = {row["code"]: row for row in served["rows"]}
    for code in chart.PENDING_FINANCE_RE_SIGN_BOOKS:
        assert (
            rows[code]["finance_signed"] is False
        ), f"{code} is served as finance-signed and finance has not signed it"
    # And the named route the signature has to come through travels with it.
    assert "HUMAN-GUIDE §6" in served["utility_books_source"]


# ═══════════════════════════════════════════════════════════════════════════
# tc4 — THE REFUSALS: what is NOT seeded, and why, as data
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc4__a_fact_the_product_already_posts_gets_no_second_account():
    """The rule that decides the set, asserted from the other side.

    Thirteen reference rows name a fact this product already posts SOMEWHERE.
    Seeding them would produce an account that will always read zero while a
    human reconciles against it — `1220 Customer AR – Electric` looks like the
    account electric receivables land in, and every receivable in this product
    posts through the ONE `accounts_receivable` designation, which
    `uq_ledger_accounts_designation` makes unique per LIVE account per tenant.

    The refusals are DATA rather than a paragraph so that CR-061's
    reconciliation can be recomputed from the code, which is what the PO asked
    for in the words *"complete 61 based on actual code"*.
    """
    seeded = {
        row.code
        for row in chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
    }
    for reference_row, code in ALREADY_POSTED_ELSEWHERE.items():
        assert (
            reference_row in chart.UTILITY_BOOKS_NOT_SEEDED
        ), f"reference row {reference_row} is neither seeded nor refused with a reason"
        if code in seeded:
            # 1200, 1210 and 4620/4750/6420's homes ARE seeded — under OUR
            # number and OUR name. The point is that no SECOND account exists.
            continue
        assert code not in seeded

    # Every refusal names a reason a person can read; a bare key would be a gap
    # wearing a ruling's clothes.
    for reference_row, reason in chart.UTILITY_BOOKS_NOT_SEEDED.items():
        assert isinstance(reference_row, int) and 1 <= reference_row <= 111
        assert len(reason) > 40, f"row {reference_row}'s reason is too short to be one"

    # 1290 Allowance for doubtful accounts is the one row left to a NAMED owner
    # rather than refused on the rule above — CR-060 T15, an open finance
    # decision. Write-off is direct today: DR 6900 / CR 1200.
    assert "1290" not in seeded
    assert "T15" in chart.UTILITY_BOOKS_NOT_SEEDED[16]


# ═══════════════════════════════════════════════════════════════════════════
# tc5 — PROVISIONING: a fresh utility gets all 125, each with its heading
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc5__a_fresh_tenant_is_seeded_all_125_accounts_categorised(brazos):
    """CR-010 B-9, PO 2026-08-17: *"9 - A full ~40 accounts for every tenant"*
    and *"more is better ; less is contraint"*. It is 125 now.

    The heading is written AT SEED TIME and travels with the row, which is what
    makes it survive a renumber (US-LED-005 rule 1). Deriving it from the code
    would break the day a utility numbers receivables 1150 — the worked example
    US-LED-005 is written around, and the exact thing `chart.py`'s banner
    forbids.
    """
    with tenant_ctx(brazos):
        served = ledger_services.chart_of_accounts()
    rows = {row["code"]: row for row in served["rows"]}
    assert len(rows) == TOTAL_PROVISIONED

    by_chart = {
        row.code: row.category
        for row in chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
    }
    for code, expected in by_chart.items():
        assert (
            rows[code]["category"] == expected
        ), f"{code} is served under {rows[code]['category']!r}, chart.py says {expected!r}"

    # A few the PO would recognise from their own chart, spot-checked by name so
    # a rename is a RED rather than a silent drift.
    assert rows["1500"]["name"] == "Land"
    assert rows["2000"]["name"] == "Vendor accounts payable"
    assert rows["9020"]["name"] == "Unrestricted net position"
    # The vocabulary is PUBLISHED, never hardcoded on the screen (BR-REP-006).
    assert list(served["categories"]) == list(chart.CHART_CATEGORIES)


# ═══════════════════════════════════════════════════════════════════════════
# tc6 — THE FILTER, including the group a pre-2026-09-02 database is all in
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc6__the_category_filter_answers_and_none_is_a_real_value(brazos, dana):
    """BR-SHL-011's `f.<name>` grammar, and the one value that is easy to miss.

    `f.category=none` is the UNCATEGORISED group. It is a real filter value
    rather than an absent one, because on any database provisioned before
    2026-09-02 it is the ONLY group there is — nothing backfills — and a filter
    that could not name it would leave a utility unable to find the rows it has
    to file.
    """
    with tenant_ctx(brazos):
        plant = ledger_services.chart_of_accounts(category=chart.CAT_FIXED_ASSETS)
        assert {row["code"] for row in plant["rows"]} == {
            row.code for row in chart.UTILITY_BOOKS_CHART if row.category == chart.CAT_FIXED_ASSETS
        }
        assert len(plant["rows"]) == 10

        # Nothing is uncategorised on a chart seeded today...
        assert ledger_services.chart_of_accounts(category="none")["rows"] == ()

        # ...until a tenant adds its own account without filing it, which is
        # lawful and is what the group is for.
        ledger_services.create_account(
            dana, code="1150", name="Trade debtors", type="asset", category=None
        )
        loose = ledger_services.chart_of_accounts(category="none")
        assert [row["code"] for row in loose["rows"]] == ["1150"]
        assert loose["rows"][0]["category"] is None


# ═══════════════════════════════════════════════════════════════════════════
# tc7 — THE TYPED ADD: a heading is validated, never invented
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc7__an_unknown_heading_is_refused_rather_than_stored(brazos, dana):
    """A heading nothing groups under is a row that vanishes from the screen it
    was typed on, so it is refused with its own message key.

    ⚠ **AND THE REFUSAL IS IN PYTHON, NOT IN A DATABASE `CHECK`** — deliberately
    unlike `designation`, whose CHECK is INLINED by Django's serializer and cost
    `ledger/0006` a whole migration to extend. A category is a GROUPING and not
    a posting pointer, so an eighteenth heading is a one-line change in
    `chart.py` with no migration behind it.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            ledger_services.create_account(
                dana, code="1155", name="Nowhere", type="asset", category="not_a_heading"
            )
        assert caught.value.message_key == "ledger.chart.category_unknown"
        assert not ledger_models.LedgerAccount.objects.filter(
            tenant_id=brazos.id, code="1155"
        ).exists()

        made = ledger_services.create_account(
            dana,
            code="1156",
            name="Bond reserve cash",
            type="asset",
            category=chart.CAT_CASH,
        )
        assert made["category"] == chart.CAT_CASH


# ═══════════════════════════════════════════════════════════════════════════
# tc8 — NOTHING POSTED MOVES, AND NEITHER DOES A FROZEN FIGURE
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_s1_tc8__the_new_rows_carry_no_designation_and_post_nothing(brazos):
    """CLAUDE.md hard rule 4, and the reason this change is safe at all.

    **Not one of the 67 carries a `designation`.** A designation is the pointer
    the posting service resolves an entry through, and there are exactly
    thirteen, all already placed. So no bill, payment, deposit or write-off can
    reach any of these accounts by accident: they are reachable only through the
    S57 manual journal entry a human writes, which is the whole point.

    This is also why no ❄️ frozen figure moves — a chart heading and an account
    nothing posts to cannot change an amount. Asserted here as *no designation
    moved*, which is the mechanism; the figures themselves are G61's 130 and
    `03-golden-verify.py`'s 33, both unchanged and both outside a pytest.
    """
    assert [row.code for row in chart.UTILITY_BOOKS_CHART if row.designation is not None] == []

    with tenant_ctx(brazos):
        served = ledger_services.chart_of_accounts()
    placed = {row["designation"]: row["code"] for row in served["rows"] if row["designation"]}
    # ⚠ **MOVED 2026-09-03 (`DEF-3441`). THIS ASSERTED THAT EVERY DESIGNATION IS
    # PLACED AT PROVISIONING AND HAD BEEN RED SINCE 2026-09-02**, when `CR-060`
    # T7b moved two of them to a place-on-first-use top-up; T15 added a third on
    # 2026-09-03, claimed only when a tenant switches the allowance policy on.
    # The claim is unchanged in spirit — every designation is placed unless it is
    # one of the ENUMERATED first-use ones, so a designation that quietly stops
    # being placed still goes RED.
    assert set(placed) == set(chart.GL_DESIGNATIONS) - set(chart.DESIGNATED_ON_FIRST_USE)
    pre_existing = {
        row.code
        for row in chart.SEED_CHART + chart.COST_OF_SERVICE_CHART + chart.WIDENED_COST_CHART
        # DEF-3441 — 5700 Depreciation expense joined the seed on 2026-09-02
        # (CR-060 T7f) CARRYING its designation, so it is a legitimate home for
        # one and this set had been red since that day.
        + chart.PERIOD_MATCHING_CHART
    }
    assert set(placed.values()) <= pre_existing


# ═══════════════════════════════════════════════════════════════════════════
# tc9 — THE RECONCILIATION, RECOMPUTED FROM THE CODE ON EVERY RUN
# ═══════════════════════════════════════════════════════════════════════════
#: `CR-061` §5's 111 reference rows, mapped to the code that answers each one:
#: reference row number -> (their code, their name, OUR code or None).
#:
#: ⚠ **THIS EXISTS BECAUSE THE PO ASKED FOR IT BY NAME.** Their instruction on
#: 2026-09-02 was *"complete 61 based on actual code"*, and the reason is a
#: measured one: the change register's ticks go stale — on a sibling CR, 70 of
#: 71 rows read outstanding for work that had shipped and nobody ticked. A table
#: in a change request is a claim; this is the same table recomputed on every
#: run against `chart.py`, so a row that quietly stops being built goes RED.
#:
#: **`None` means DELIBERATELY NOT SEEDED**, and every one of those has its
#: reason in `chart.UTILITY_BOOKS_NOT_SEEDED` — asserted below, so a refusal can
#: never decay into a silent gap.
REFERENCE_CHART = {
    1: ("1000", "Operating Cash", "1000"),
    2: ("1010", "Restricted Cash", "1060"),
    3: ("1020", "Petty Cash", "1020"),
    4: ("1030", "Bank Clearing", "1030"),
    5: ("1040", "ACH Clearing", "1040"),
    6: ("1050", "Credit Card Clearing", "1050"),
    7: ("1100", "Investments", "1100"),
    8: ("1110", "Interest Receivable", "1110"),
    9: ("1200", "Customer AR - Water", None),
    10: ("1210", "Customer AR - Sewer", None),
    11: ("1220", "Customer AR - Electric", None),
    12: ("1230", "Customer AR - Gas", None),
    13: ("1240", "Customer AR - Submeter", None),
    14: ("1250", "Non-Customer AR", "1250"),
    15: ("1260", "Unbilled Revenue", None),
    16: ("1290", "Allowance for Doubtful Accounts", None),
    17: ("4000", "Water Consumption", "4110"),
    18: ("4010", "Water Base Charge", "4115"),
    19: ("4020", "Water Service Charge", None),
    20: ("4100", "Sewer Consumption", "4120"),
    21: ("4110", "Sewer Base Charge", None),
    22: ("4200", "Stormwater Charge", "4160"),
    23: ("4300", "Electric Energy Revenue", "4100"),
    24: ("4310", "Electric Demand Revenue", None),
    25: ("4320", "Electric Fixed Charge", "4105"),
    26: ("4400", "Gas Consumption", "4140"),
    27: ("4500", "Submeter Consumption", None),
    28: ("4600", "Connection Fee", "4600"),
    29: ("4610", "Reconnection Fee", "4610"),
    30: ("4620", "Late Payment Fee", None),
    31: ("4630", "Meter Fee", "4630"),
    32: ("4700", "Billing Adjustment", "4700"),
    33: ("4710", "Leak Adjustment", "4710"),
    34: ("4720", "Rate Correction", "4720"),
    35: ("4730", "Customer Credit", "4730"),
    36: ("4740", "Refunds", "4740"),
    37: ("4750", "Bad Debt Write-off", None),
    38: ("2300", "Residential Deposit", "2300"),
    39: ("2310", "Commercial Deposit", None),
    40: ("2320", "Developer Deposit", None),
    41: ("2330", "Meter Deposit", None),
    42: ("2340", "Advance Customer Payment", None),
    43: ("2000", "Vendor AP", "2000"),
    44: ("2010", "Contractor AP", "2010"),
    45: ("2020", "Retainage Payable", "2020"),
    46: ("2100", "Accrued Expenses", "2100"),
    47: ("2110", "Accrued Payroll", "2110"),
    48: ("2120", "Accrued Interest", "2120"),
    49: ("1300", "Meter Inventory", "1300"),
    50: ("1310", "Pipe & Fittings", "1310"),
    51: ("1320", "Electrical Equipment", "1320"),
    52: ("1330", "Chemicals (inventory)", "1330"),
    53: ("1340", "General Materials", "1340"),
    54: ("6100", "Inventory Consumption", "5260"),
    55: ("1500", "Land", "1500"),
    56: ("1510", "Water Source & Supply", "1510"),
    57: ("1520", "Water Treatment Plant", "1520"),
    58: ("1530", "Water Distribution System", "1530"),
    59: ("1540", "Sewer Collection System", "1540"),
    60: ("1550", "Wastewater Treatment Plant", "1550"),
    61: ("1560", "Electric Generation", "1560"),
    62: ("1570", "Electric Distribution", "1570"),
    63: ("1580", "Gas Distribution", "1580"),
    64: ("1590", "Meters", "1590"),
    65: ("1600", "Construction in Progress", "1600"),
    66: ("1610", "Engineering Costs", "1610"),
    67: ("1620", "Capitalized Labor", "1620"),
    68: ("1630", "Capitalized Overhead", "1630"),
    69: ("1640", "Developer-Funded CIP", "1640"),
    70: ("1700", "Water Plant Depreciation", "1700"),
    71: ("1710", "Sewer Plant Depreciation", "1710"),
    72: ("1720", "Electric Plant Depreciation", "1720"),
    73: ("1730", "Meter Depreciation", "1730"),
    74: ("6000", "Salaries & Wages", "5500"),
    75: ("6010", "Employee Benefits", "5500"),
    76: ("6020", "Overtime", None),
    77: ("6100", "Electricity Purchased", "5100"),
    78: ("6110", "Water Purchased", "5110"),
    79: ("6120", "Gas Purchased", "5140"),
    80: ("6200", "Chemicals", "5240"),
    81: ("6210", "Fuel", None),
    82: ("6300", "Repairs & Maintenance", None),
    83: ("6310", "Meter Maintenance", "5250"),
    84: ("6320", "Vehicle Maintenance", None),
    85: ("6400", "Billing Operations", None),
    86: ("6410", "Payment Processing Fees", "5430"),
    87: ("6420", "Bank Fees", None),
    88: ("6500", "IT / SaaS", "5550"),
    89: ("6510", "Cloud Services", "5560"),
    90: ("2500", "Revenue Bonds", "2500"),
    91: ("2510", "Bank Loans", "2510"),
    92: ("2520", "Current Portion of Debt", "2520"),
    93: ("2530", "Lease Liability", "2530"),
    94: ("2540", "Interest Payable", "2540"),
    95: ("7000", "Interest Expense", "7000"),
    96: ("3000", "Capital Grant", "3040"),
    97: ("3010", "Operating Grant", "3010"),
    98: ("3020", "Developer Contribution", "3020"),
    99: ("3030", "Customer Contribution", "3030"),
    100: ("7100", "Interest Income", "7100"),
    101: ("7110", "Investment Income", "7110"),
    102: ("7120", "Gain on Asset Disposal", "7120"),
    103: ("7130", "Loss on Asset Disposal", "7130"),
    104: ("8000", "Transfer In - General Fund", "8000"),
    105: ("8010", "Transfer Out - Utility", "8010"),
    106: ("8020", "Water to Sewer Transfer", "8020"),
    107: ("8030", "Utility to General Fund", "8030"),
    108: ("9000", "Net Investment in Capital Assets", "9000"),
    109: ("9010", "Restricted Net Position", "9010"),
    110: ("9020", "Unrestricted Net Position", "9020"),
    111: ("9030", "Prior Period Adjustment", "9030"),
}


def test_cr061_s1_tc9__all_111_reference_rows_reconcile_against_the_code():
    """**21 already built · 67 built here · 23 refused with a reason = 111.**

    The three numbers this CR is reported on, recomputed rather than quoted.
    `CR-061` §5 said only *"the product seeds 34 accounts; the reference has
    111"* and named NOT ONE of the rows the product already had — including the
    seven `CR-066` had landed that same morning at the reference's own numbers
    (4600, 4610, 4630 and the 4700-4730 block). That is the stale tick the PO
    was pointing at with *"based on actual code"*.

    Every arm of this is a real failure mode:
      * a reference row pointing at a code the chart does not hold is a MAP that
        rotted — the account was renamed, renumbered or dropped;
      * a `None` with no reason in `chart.UTILITY_BOOKS_NOT_SEEDED` is a refusal
        that has decayed into a silent gap;
      * a reason recorded for a row that IS seeded is the opposite error, and it
        is the one that was actually there (row 54, corrected the same day).
    """
    assert sorted(REFERENCE_CHART) == list(range(1, 112)), "the reference is 111 rows"

    every = (
        chart.SEED_CHART
        + chart.COST_OF_SERVICE_CHART
        + chart.WIDENED_COST_CHART
        + chart.UTILITY_BOOKS_CHART
    )
    by_code = {row.code: row for row in every}
    new_here = {row.code for row in chart.UTILITY_BOOKS_CHART}

    already, built_here, refused = [], [], []
    for number in sorted(REFERENCE_CHART):
        _, _, ours = REFERENCE_CHART[number]
        if ours is None:
            assert (
                number in chart.UTILITY_BOOKS_NOT_SEEDED
            ), f"reference row {number} is neither seeded nor refused with a reason"
            refused.append(number)
            continue
        assert (
            ours in by_code
        ), f"reference row {number} points at {ours}, which the chart does not hold"
        (built_here if ours in new_here else already).append(number)

    assert len(already) == 21, sorted(already)
    assert len(built_here) == 67, len(built_here)
    assert len(refused) == 23, sorted(refused)
    assert len(already) + len(built_here) + len(refused) == 111

    # The reverse direction: no reason is recorded for a row that IS seeded.
    seeded_numbers = {n for n in REFERENCE_CHART if REFERENCE_CHART[n][2] is not None}
    assert set(chart.UTILITY_BOOKS_NOT_SEEDED) == set(REFERENCE_CHART) - seeded_numbers

    # And the seven CR-066 landed at the reference's own numbers, which is the
    # tick CR-061 §5 never carried.
    for number in (28, 29, 31, 32, 33, 34, 35):
        their_code, _, ours = REFERENCE_CHART[number]
        assert ours == their_code, number
        assert not by_code[ours].signed, "CR-066 approved the MAPPING, not the chart"
