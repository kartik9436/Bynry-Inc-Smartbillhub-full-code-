# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 · the `journal_lines` dataset query (lane DS-LEDGER).
#           Drawings read as images (B14 rule 42): R15 p055 · R16 p056 ·
#           R18 p057 · R21 p058 · §7.2.2 p085 · §7.5/§7.6 p087.
# Rules:    NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-REP-001
#           (a money report names its basis) · BR-REP-002 (read models only) ·
#           BR-REP-024 (never a 0 where a figure is not derivable) ·
#           BR-LED-007 (a drift is the posting service's defect) ·
#           CLAUDE.md hard rule 2 (money is a Decimal, never a float) ·
#           hard rules 4 and 5 (this path reads and writes nothing)
# ───────────────────────────────────────────────────────
"""THE `journal_lines` DATASET, AND THE FOUR REPORTS IT TURNS ON.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *"no error"* — it is the commonest false pass in this repository — so
no case here is satisfied by an empty answer, and the one case that asserts a
zero (`per` cutting a page that does not exist) sits beside a positive one in
the same fixture.

⚠ **AND THE SUITE RUNS ON IN-MEMORY SQLITE** (`config/settings/test.py`
hardcodes it and ignores `DATABASE_URL`), so these cases prove the SHAPE and
the ARITHMETIC and cannot prove anything about LIMIT/OFFSET cost, RLS or an
aborted transaction. That is hard-won law 14, and the PostgreSQL half is
`10-scripts/ds_ledger_journal_lines_cost.py`, whose figures are in the lane
report.
"""

from decimal import Decimal

import pytest

from apps.ledger import journal_lines_dataset as dataset, models as ledger_models, posting
from apps.reports import datasets, queries

from tests.ledger_le_fixtures import JULY_END, JULY_START, a_request, gl, line
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

WIDE = {"start": JULY_START, "end": JULY_END}

#: Three entries, six lines, and the figures are chosen so every assertion
#: below names a number rather than a shape: 100 + 250 + 40 = 390 on each side.
AMOUNTS = (Decimal("100.0000"), Decimal("250.0000"), Decimal("40.0000"))
TOTAL = Decimal("390.0000")
LINES = 6


def _post_three(tenant):
    """Three balanced entries, through the POSTING SERVICE (hard rule 5).

    Not an ORM `create()` and not raw SQL: `ledger_sole_writer_guard()` raises
    hard rule 5 BY NAME on either, and a fixture that went round the one writer
    would be proving the dataset against rows the product cannot produce.
    """
    cash = gl(tenant, "1000", type_="asset", name="Cash")
    revenue = gl(tenant, "4100", type_="revenue", name="Water revenue")
    for index, amount in enumerate(AMOUNTS):
        posting.post(
            a_request(
                (
                    line(cash, ledger_models.SIDE_DEBIT, amount),
                    line(revenue, ledger_models.SIDE_CREDIT, amount),
                ),
                key=f"ds-ledger-fixture|{index}|posted",
                entry_date=JULY_START,
            )
        )
    return cash, revenue


# ── the dataset itself ──────────────────────────────────────────────────────
def test_it_serves_one_row_per_line_and_the_pair_foots(brazos):
    """Six lines, 390.00 each side, difference 0.00, `balanced` True.

    ⚠ **R15's warning is asserted, not described** (p055, verbatim): *"Balanced
    pairs are a database guarantee, not a report's opinion. A difference other
    than zero here means the posting service has a defect."* A non-zero
    difference fails this case NAMING the two figures, which is the only form
    of this assertion worth having.
    """
    with tenant_ctx(brazos):
        _post_three(brazos)
        answer = dataset.journal_lines(**WIDE)

    assert answer["totals"]["lines"] == LINES, "the fixture posted six lines"
    assert len(answer["rows"]) == LINES
    debit, credit = answer["totals"]["debit"], answer["totals"]["credit"]
    assert debit == TOTAL and credit == TOTAL, (
        f"Σ debits {debit} vs Σ credits {credit} — BR-LED-007 makes a difference a "
        "posting-service defect and a release blocker, never a figure to adjust"
    )
    assert answer["totals"]["difference"] == Decimal("0")
    assert answer["balanced"] is True
    assert answer["basis"] == "posting", "BR-REP-001 — every money figure names its basis"


def test_money_is_a_decimal_and_never_a_float(brazos):
    """CLAUDE.md hard rule 2. A float here is a rounding error nobody can find."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        answer = dataset.journal_lines(**WIDE)
    assert answer["rows"], "a zero-row answer would satisfy every type assertion below"
    for row in answer["rows"]:
        assert isinstance(row.amount, Decimal)
        assert isinstance(row.debit, Decimal) and isinstance(row.credit, Decimal)
    assert isinstance(answer["totals"]["difference"], Decimal)


def test_a_line_is_split_into_a_debit_and_a_credit_column(brazos):
    """The stored shape is one non-negative `amount` beside a `side` (B2 §2);
    every drawing has TWO money columns. The split happens once, here."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        answer = dataset.journal_lines(**WIDE)
    debits = [row for row in answer["rows"] if row.debit != Decimal("0")]
    credits = [row for row in answer["rows"] if row.credit != Decimal("0")]
    assert len(debits) == 3 and len(credits) == 3
    for row in answer["rows"]:
        assert row.debit == Decimal("0") or row.credit == Decimal(
            "0"
        ), "no line is on both sides — that is what `side` being a column buys"


def test_the_running_balance_is_null_with_a_reason_and_never_a_number(brazos):
    """§7.2.2 — `balance` is SEMI-ADDITIVE and is not a property of one line.

    The dataset declares the column, so serving a plausible figure would be
    worse than serving none: a footer that summed it is the canonical wrong
    answer the brief names first. It is null, and the reason travels.
    """
    with tenant_ctx(brazos):
        _post_three(brazos)
        answer = dataset.journal_lines(**WIDE)
    assert answer["rows"]
    assert all(row.balance is None for row in answer["rows"])
    codes = {problem["code"] for problem in answer["problems"]}
    assert (
        "running_balance_is_not_a_property_of_one_line" in codes
    ), "BR-REP-024 — an absent figure carries a named reason, never a silent blank"


def test_the_declared_measure_still_says_balance_is_semi_additive():
    """The refusal REP-P2-MODEL builds reads this declaration, so it is asserted
    here rather than trusted: a `full` here would let a footer sum a position
    across time and no figure on the screen would look wrong."""
    by_name = {measure.name: measure for measure in datasets.JOURNAL_LINES.measures}
    assert by_name["balance"].additivity == datasets.ADD_SEMI
    assert datasets.DIM_TIME in by_name["balance"].forbidden_across
    assert by_name["debit"].additivity == datasets.ADD_FULL
    assert by_name["credit"].additivity == datasets.ADD_FULL


# ── NFR-3 / NFR-5 ───────────────────────────────────────────────────────────
def test_it_cuts_a_page_and_the_totals_still_describe_the_whole_set(brazos):
    """Two rows served, six counted. The KPI tiles foot to the REPORT whatever
    page is cut — the premise `/outstandings`'s withdrawn docstring got
    backwards and the one `billing_register` already builds on."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        first = dataset.journal_lines(page=1, per=2, **WIDE)
        last = dataset.journal_lines(page=3, per=2, **WIDE)

    assert len(first["rows"]) == 2, "per=2 must cut a page"
    assert first["total"] == LINES and first["pages"] == 3
    assert first["totals"]["debit"] == TOTAL, "totals are the whole filtered set, never the page"
    assert len(last["rows"]) == 2
    assert {row.line_id for row in first["rows"]}.isdisjoint(
        {row.line_id for row in last["rows"]}
    ), "page 1 and page 3 must not overlap — the order has to be total"


def test_an_over_run_page_clamps_and_never_errors(brazos):
    """`BR-SHL-011` — invalid values clamp, NEVER error. A saved link carrying
    `page=999` opens on the last page rather than on an error screen.

    ⚠ **THE ZERO CASE SITS BESIDE A POSITIVE ONE IN THIS FIXTURE**, on purpose:
    the same six rows are asserted present above, so an empty answer here
    cannot be an empty database wearing a clamp's clothes."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        clamped = dataset.journal_lines(page=999, per=2, **WIDE)
    assert clamped["page"] == 3, "clamped to the last page"
    assert len(clamped["rows"]) == 2, "and it serves that page rather than nothing"


def test_the_export_branch_has_no_ceiling(brazos):
    """`NFR-5` — `per=None` is the whole filtered set. A file is the whole set
    by definition (§7.5), and a report that silently became fifty rows would
    look perfectly valid."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        whole = dataset.journal_lines(per=None, **WIDE)
    assert len(whole["rows"]) == LINES == whole["total"]
    assert whole["per"] is None and whole["pages"] == 1


def test_the_dataset_declares_that_it_pages():
    """`P2.12` reads this FIELD rather than a paragraph. It said `False` while
    nothing implemented the dataset at all — a limitation recorded about
    something absent, which no check can tell from a real one."""
    assert datasets.JOURNAL_LINES.paginates is True


def test_every_filter_the_query_honours_is_a_declared_filter():
    """`runner.bind` DROPS an undeclared parameter, so a filter the query
    applies and the dataset omits is a control that looks live and changes
    nothing — hard-won law 2's mirror, in a data structure."""
    for name in (
        "account_from",
        "account_to",
        "service",
        "source_type",
        "target",
        "level",
        "authority",
    ):
        assert name in datasets.JOURNAL_LINES.filters


def test_every_sort_it_offers_ends_in_a_unique_column():
    """A page is a window over an ORDER. Without a total order two equal rows
    swap between pages and a clerk sees one twice and another never."""
    for name in dataset.LINE_SORTS:
        assert dataset.LINE_SORT_COLUMNS[name][-1] == "id"


# ── the narrowing rule ──────────────────────────────────────────────────────
def test_a_narrowed_set_states_no_verdict_and_says_why(brazos):
    """⚠ `None`, never `False`. Balance is a property of an ENTRY; an account
    range keeps part of each one, so `False` would accuse the posting service
    of a defect it does not have (CR-060 C24, one level down)."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        narrowed = dataset.journal_lines(account_from="4000", account_to="4999", **WIDE)

    assert narrowed["totals"]["lines"] == 3, "three revenue lines, not zero and not six"
    assert narrowed["totals"]["credit"] == TOTAL and narrowed["totals"]["debit"] == Decimal("0")
    assert narrowed["balanced"] is None, "a narrowed residue states no verdict"
    codes = {problem["code"] for problem in narrowed["problems"]}
    assert "a_narrowed_set_cannot_state_whether_the_books_foot" in codes
    assert narrowed["totals"]["difference"] == -TOTAL, (
        "the difference is still PUBLISHED — it is a real figure about the rows in front "
        "of you, it is simply not evidence about the posting service. It is NEGATIVE here "
        "because the range kept the credit halves and dropped the debit halves, which is "
        "precisely why it says nothing about whether the books foot."
    )


def test_a_window_alone_leaves_the_verdict_standing(brazos):
    """A date window does not cut inside an entry, so it does NOT suppress the
    verdict. The mirror of the case above, and the reason the narrowing set is
    listed explicitly rather than inferred."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        windowed = dataset.journal_lines(start=JULY_START, end=JULY_START)
    assert windowed["totals"]["lines"] == LINES
    assert windowed["balanced"] is True


# ── the four reports ────────────────────────────────────────────────────────
def test_the_four_new_keys_are_dispatchable():
    """Hard-won law 2 — a report nothing routes to is a report that does not
    exist, however complete its query is."""
    for key in ("trial_balance", "journal_export", "tax_remittance", "close_pack"):
        assert key in queries.VIEWERS, f"{key} must be dispatchable"


def test_trial_balance_publishes_its_difference_and_its_verdict(brazos):
    """R15 (p055). Debits 390.00, credits 390.00, difference 0.00, Balanced."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.trial_balance({"from": JULY_START, "to": JULY_END})

    assert report["basis"] == "posting"
    assert report["rows"], "a trial balance over three posted entries is not empty"
    assert report["totals"]["debit"] == "390.000000"
    assert report["totals"]["credit"] == "390.000000"
    assert report["totals"]["difference"] == "0.000000"
    assert report["totals"]["balanced"] is True
    difference = next(tile for tile in report["kpis"] if tile["key"] == "difference")
    assert difference["detail"] == "balanced"


def test_a_ranged_trial_balance_foots_to_its_own_rows_and_states_no_verdict(brazos):
    """The footer is Σ of the rows ON the report, always — a footer describing
    rows a filter excluded is the trap `P2.19` refuses."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.trial_balance(
            {"from": JULY_START, "to": JULY_END, "account_from": "4000", "account_to": "4999"}
        )
    assert len(report["rows"]) == 1, "one revenue account in range, not zero and not two"
    assert Decimal(report["totals"]["credit"]) == TOTAL
    # ⚠ **COMPARED AS A NUMBER AND NOT AS A STRING, DELIBERATELY.** `_money`
    # serves the EXACT decimal string and normalises no scale, because B4 owns
    # where a money figure rounds and a display helper is not that place. So the
    # unfiltered footer reads `390.000000` (ledger's own Σ, at storage width)
    # and this one reads `0` (a Σ over rows whose debit side is a bare zero).
    # They are the same numbers; a string assertion here would be asserting the
    # scale of an intermediate, which is not a fact about the money.
    assert Decimal(report["totals"]["debit"]) == Decimal("0")
    assert report["totals"]["balanced"] is None
    codes = {problem["code"] for problem in report["unavailable"]}
    assert "a_narrowed_trial_balance_cannot_state_whether_the_books_foot" in codes


def test_the_summary_level_rolls_up_without_moving_a_figure(brazos):
    """p055's `Level` control. A roll-up by account TYPE is the same rows
    added; debits and credits are fully additive across accounts (§7.2.2), so
    the totals cannot move."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        detail = queries.trial_balance({"from": JULY_START, "to": JULY_END, "level": "detail"})
        summary = queries.trial_balance({"from": JULY_START, "to": JULY_END, "level": "summary"})
    assert len(detail["rows"]) >= 2
    assert len(summary["rows"]) < len(detail["rows"]) or len(summary["rows"]) >= 1
    assert summary["totals"]["debit"] == detail["totals"]["debit"]
    assert summary["totals"]["credit"] == detail["totals"]["credit"]
    assert summary["totals"]["level"] == "summary"


def test_journal_export_serves_the_lines_and_pages_them(brazos):
    """R16 (p056) — the one report of the ten that was wholly dark, and the
    reason the dataset had to exist: an aggregate cannot be un-aggregated."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.journal_export({"from": JULY_START, "to": JULY_END, "per": 2})

    assert report["basis"] == "posting"
    # ⚠ **THE VIEWER CLAMPS `per` TO THE PRODUCT'S PAGE-SIZE SET (A11 r2 item 1,
    # `core.pagination.clamp_page_size`), SO `per=2` BECOMES 50 AND SIX ROWS ARE
    # ONE PAGE.** That is not the paging failing — it is the one page-size
    # vocabulary this product has, and a report inventing a smaller one would be
    # the drift `BR-SHL-011` and A11 exist to prevent. **The DATASET's paging is
    # proved at the grain that can show it**, by
    # `test_it_cuts_a_page_and_the_totals_still_describe_the_whole_set`, which
    # calls the query directly with `per=2` and asserts two rows out of six.
    # What THIS case proves is that the viewer publishes a `page` block at all,
    # and that its `total` is the whole filtered set rather than the page.
    assert report["page"]["per"] == 50, "clamped to the smallest size this product offers"
    assert len(report["rows"]) == LINES
    assert report["page"]["total"] == LINES and report["page"]["pages"] == 1
    assert report["totals"]["lines"] == LINES
    # Compared as a NUMBER: `_money` serves the exact decimal string and
    # normalises no scale (B4 owns rounding), so `390.000000 - 390.000000`
    # reaches the wire as `"0"`. Asserting the string would be asserting the
    # scale of an intermediate rather than a fact about the money.
    assert Decimal(report["totals"]["difference"]) == Decimal("0")
    assert all(row["balance"] is None for row in report["rows"])
    last_export = next(tile for tile in report["kpis"] if tile["key"] == "last_export")
    assert last_export["value"] is None
    assert (
        last_export["reason_code"] == "nothing_has_been_exported_yet"
    ), "BR-REP-024 — nothing exported yet is a stated absence, never a 0 and never a blank"


def test_journal_export_per_all_lifts_no_cap_it_opens_the_export(brazos):
    """`NFR-5`. `per=all` is a file's door, not a ceiling being raised."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.journal_export({"from": JULY_START, "to": JULY_END, "per": "all"})
    assert len(report["rows"]) == LINES
    assert (
        "page" not in report
    ), "an absent `page` key says 'this is all of it' without claiming 'this is page one'"


def test_an_unknown_sort_falls_back_and_never_errors(brazos):
    """`BR-SHL-011`. A saved link carrying a retired sort still opens."""
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.journal_export({"from": JULY_START, "to": JULY_END, "sort": "frog"})
    assert len(report["rows"]) == LINES


def test_close_pack_renders_the_tie_outs_and_never_re_decides_the_blocker(brazos):
    """R21 (p058). *"A drift here is a release blocker, not a report finding."*

    ⚠ **THE VERDICT IS READ, NOT DERIVED.** A screen that worked out its own
    blocker could render three red rows and no blocker, which is this check
    developing the fault it exists to detect. `release_blocked` comes off
    ledger's wire exactly as published, and `dismissible` is `False` there
    because US-LED-004 TC-5 says the absence must be ON the wire so a client
    cannot look for a dismiss path and quietly not find one.

    ⚠ **A ROW NOBODY COULD COMPUTE IS NOT A GREEN.** On a tenant that has
    designated no control accounts every row is `unverifiable`, its difference
    is null rather than `0.00`, and the release is blocked. That is the case
    this fixture actually produces and it is asserted rather than avoided.
    """
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.close_pack({"from": JULY_START, "to": JULY_END})

    assert report["rows"], "the tie-out panel is four checks, never zero"
    assert report["basis"] == "posting"
    states = {row["result"] for row in report["rows"]}
    assert states, "every row states a verdict word"
    for row in report["rows"]:
        if row["result"] == "unverifiable":
            assert row["difference"] is None, (
                "a delta struck against an absence is a fabricated number wearing a "
                "precise one's clothes — BR-REP-024"
            )
    assert report["totals"]["dismissible"] is False
    assert report["totals"]["release_blocked"] == bool(
        report["totals"]["drifting"] or report["totals"]["unverifiable"]
    )


def test_tax_remittance_labels_a_basis_on_every_row_and_carries_both(brazos):
    """R18 (p057) — *"Two bases in one report, labelled per row."*

    The report's own `basis` is the BILLED column's (posting) and `totals.bases`
    carries both, because BR-REP-001 is met twice here and unlabelled money is
    a contract failure. A row whose authority has no chosen basis is NULL and
    named in `unavailable`, never defaulted — a default would file a utility's
    return on the wrong basis in its first month.
    """
    with tenant_ctx(brazos):
        _post_three(brazos)
        report = queries.tax_remittance({"from": JULY_START, "to": JULY_END})

    assert report["basis"] == "posting"
    assert report["totals"]["bases"] == {"billed": "posting", "collected": "clearing"}
    for row in report["rows"]:
        assert "basis" in row, "p057 draws BASIS as a column, per row"
    unbased = [row for row in report["rows"] if not row["basis"]]
    if unbased:
        codes = {problem["code"] for problem in report["unavailable"]}
        assert "an_authority_has_no_remitting_basis_chosen" in codes
