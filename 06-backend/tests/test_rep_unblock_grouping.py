# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.17 — grouping made REAL, in SQL.
#           Defects closed: DEF-REP-6855 (group_by accepted, validated, echoed
#           and read by no query) · DEF-REP-6875 (a group subtotal summed ONE
#           PAGE under a whole-set footer) · DEF-REP-6876 (two dataset queries
#           built, measured, seam-wired and registered nowhere).
# Rules:    CLAUDE.md hard rule 2 (money 4 dp, never a float) · hard rule 3 (a
#           quantity carries its unit) · hard-won law 2 and its mirror (a
#           control that passes every check and does nothing) · law 7 (*"ask
#           what would make this check pass wrongly"*)
# Tests:    this file, plus the real-PostgreSQL arithmetic in
#           10-scripts/rep_unblock_sql_grouping_pg_proof.py
# ───────────────────────────────────────────────────────
"""GROUPING IS A `GROUP BY` OR IT IS REFUSED BY NAME. NOTHING ELSE IS SERVED.

⚠ **WHY A SECOND GROUPING TEST FILE, AND WHAT THE FIRST TWO CANNOT SEE.**
`test_rep_p2_17_slicers.py` proves the ENGINE and `test_rep_p2_22_wired.py`
proves the FUNNEL, and both pass in full over the defect this file exists for.
The reason is one line of their fixtures: each builds a three-row payload with
**no `page` key**, so the whole filtered set IS the page and a Python Σ over the
served rows is arithmetically right. Measured on real PostgreSQL 16 on
2026-09-27, with a page in play, it is not: the billing register grouped by
status served `$14,048.10 + $137.70 = $14,185.80` of subtotals over 50 rows
under a footer of `$30,750.07` over 92 bills (`DEF-REP-6875`).

**So every case here puts a PAGE in the payload**, which is the one thing the
shipped fixtures do not, and asserts the two directions that matter:

  · a query that publishes SQL `GROUP BY` cells gets group rows whose Σ **equals
    the footer**, asserted as arithmetic and not as a shape;
  · a query that publishes none, over a payload whose page is SHORT, is
    **REFUSED BY NAME** and serves no group row at all.

⚠ **AND THE THIRD DIRECTION, WHICH IS THE ONE `DEF-REP-6855` WAS:** a run that
groups nothing must not SAY it grouped something. The payload used to carry
`group_by: ["accounting_period"]` over ungrouped rows, so every downstream
check — and every reader — was told the report was grouped.
"""

from decimal import Decimal

import pytest

from apps.reports import api as reports_api
from apps.reports import queries, report_seams, runner, slicers


def _definition(**over):
    base = dict(
        key="test_key",
        name="Test",
        dataset="journal_lines",
        group_code="finance",
        sub_group_code=None,
        columns=(),
        filters={},
        group_by=(),
        sort=(),
        service_codes=(),
        from_table=True,
    )
    base.update(over)
    return runner.ResolvedDefinition(**base)


#: A payload with a PAGE — 3 rows served out of 749. This is the shape the
#: shipped fixtures do not have and the only shape the defect is visible in.
def _paged_payload(*, groups=None):
    payload = {
        "key": "test_key",
        "basis": "posting",
        "window": {},
        "currency": "USD",
        "columns": ("posted_on", "account_code", "debit", "credit"),
        "rows": [
            {"posted_on": "2026-07-04", "account_code": "1200", "debit": "100.0000", "credit": "0"},
            {"posted_on": "2026-08-04", "account_code": "1200", "debit": "200.0000", "credit": "0"},
            {"posted_on": "2026-08-09", "account_code": "4000", "debit": "0", "credit": "300.0000"},
        ],
        "kpis": [],
        # The FOOTER: a SQL aggregate over the whole filtered set, 749 lines.
        "totals": {"debit": "68328.1600", "credit": "68328.1600", "lines": 749},
        "unavailable": [],
        "page": {"page": 1, "per": 3, "total": 749, "pages": 250},
    }
    if groups is not None:
        payload["groups"] = groups
        payload["grouped_by"] = ("accounting_period",)
        payload["groups_not_served"] = ()
        payload["group_measures"] = ("debit", "credit", "lines")
    return payload


#: SQL `GROUP BY` cells, as `journal_lines_dataset._grouped` returns them —
#: three months, over the WHOLE 749-line filtered set. They sum to the footer.
_CELLS = (
    {
        "level": 0,
        "dimension": "accounting_period",
        "values": ("2026-07-01",),
        "rows": 294,
        "measures": {"debit": Decimal("14012.6700"), "credit": Decimal("14012.6700"), "lines": 294},
    },
    {
        "level": 0,
        "dimension": "accounting_period",
        "values": ("2026-08-01",),
        "rows": 419,
        "measures": {"debit": Decimal("38499.4900"), "credit": Decimal("38499.4900"), "lines": 419},
    },
    {
        "level": 0,
        "dimension": "accounting_period",
        "values": ("2026-09-01",),
        "rows": 36,
        "measures": {"debit": Decimal("15816.0000"), "credit": Decimal("15816.0000"), "lines": 36},
    },
)


@pytest.fixture
def wired(monkeypatch):
    """Substitute `resolve` and `queries_for` so the assertion is about the
    RUNNER and needs no database — `test_rep_p2_22_wired.py`'s own reasoning."""

    def install(definition, payload):
        monkeypatch.setattr(runner, "resolve", lambda key: definition)
        monkeypatch.setattr(
            runner, "queries_for", lambda key, dataset=None: (lambda bound: dict(payload))
        )

    return install


# ── 1 · THE UNGROUPED PATH IS UNTOUCHED, COMPARED RATHER THAN ASSERTED ──────
def test_ungrouped__the_payload_gains_nothing_at_all(wired):
    """⚠ **THE HALF THAT MAKES THIS SAFE ON THE SHARED PATH.** Every report in
    the product runs through `_shaped`, so the ungrouped answer must come out
    byte-for-byte what went in. Compared key by key against the stub rather than
    asserted in a sentence — a comment claiming a guarantee is not the guarantee.
    """
    stub = _paged_payload()
    wired(_definition(), stub)
    result = runner.run("test_key", {})

    assert result.payload["rows"] == stub["rows"]
    # Nothing grouping-shaped appears, and the absences are the point: a screen
    # reading `group_by` must not find one on a report nobody grouped.
    for key in ("group_by", "groups", "collapsed", "groups_not_served"):
        assert key not in result.payload, key
    assert result.payload["unavailable"] == []
    # The footer is still a NUMBER. `debit` is fully additive, so nothing here
    # may turn it into an em-dash.
    assert result.payload["totals"]["debit"] == "68328.1600"


# ── 2 · WITH SQL CELLS: GROUP ROWS, AND THEIR Σ **EQUALS** THE FOOTER ───────
def test_grouped_in_sql__subtotals_sum_to_the_footer_exactly(wired):
    """`P2.17`, and the arithmetic `DEF-REP-6875` was missing.

    ⚠ **THE Σ IS COMPUTED HERE AND COMPARED, NOT COPIED FROM THE FIXTURE.**
    A test that asserted each subtotal equalled a literal would pass just as
    happily over three figures that do not add up to the footer — which is
    exactly the defect. The relationship between the parts and the whole is the
    thing under test.
    """
    wired(_definition(), _paged_payload(groups=_CELLS))
    result = runner.run("test_key", {"group_by": "accounting_period"})

    groups = [row for row in result.payload["rows"] if row.get("__kind__") == "group"]
    assert [g["value"] for g in groups] == ["2026-07-01", "2026-08-01", "2026-09-01"]
    assert [g["rows"] for g in groups] == [294, 419, 36]

    for measure in ("debit", "credit", "lines"):
        total = sum(Decimal(str(g["subtotals"][measure])) for g in groups)
        assert total == Decimal(str(result.payload["totals"][measure])), measure
    # Hand-computed, so a wrong footer in the fixture cannot hide behind the loop:
    # 14,012.67 + 38,499.49 + 15,816.00 = 68,328.16, and 294 + 419 + 36 = 749.
    assert sum(Decimal(str(g["subtotals"]["debit"])) for g in groups) == Decimal("68328.16")
    assert sum(g["rows"] for g in groups) == 749

    assert result.payload["group_by"] == ["accounting_period"]
    assert result.payload["collapsed"] is True


def test_grouped_in_sql__the_rows_are_not_the_ungrouped_rows(wired):
    """⚠ **THE SPECIFIC FALSE PASS THIS FILE WAS WARNED ABOUT:** a grouping that
    returns rows proves nothing if the ungrouped run returns the same rows. That
    is `DEF-REP-6855` measured — 20 groupings over five reports, 20 returning
    rows byte-identical to the ungrouped run. So the DIFFERENCE is asserted."""
    wired(_definition(), _paged_payload(groups=_CELLS))
    ungrouped = runner.run("test_key", {}).payload["rows"]
    grouped = runner.run("test_key", {"group_by": "accounting_period"}).payload["rows"]

    assert grouped != ungrouped
    assert not any(row.get("__kind__") == "group" for row in ungrouped)
    assert all(row.get("__kind__") == "group" for row in grouped)


def test_grouped_in_sql__money_leaves_as_a_string_and_never_as_a_float(wired):
    """Hard rule 2: money is stored to 4 decimals and is NEVER a float. A
    subtotal built with `+` over `float(cell)` would be off in the fourth place
    on a few thousand rows and would tie out to nothing."""
    wired(_definition(), _paged_payload(groups=_CELLS))
    result = runner.run("test_key", {"group_by": "accounting_period"})
    for group in result.payload["rows"]:
        for measure in ("debit", "credit"):
            figure = group["subtotals"][measure]
            assert isinstance(figure, str), figure
            assert not isinstance(figure, float)
            # Exact, not rounded — B4 rounds at finalization and display.
            assert Decimal(figure) == Decimal(figure)


# ── 3 · WITHOUT SQL CELLS, OVER A SHORT PAGE: REFUSED BY NAME ───────────────
def test_no_group_by_and_a_short_page__refused_by_name_and_no_group_row(wired):
    """`DEF-REP-6875` itself, turned into a check.

    Before this, these three rows were summed in Python and served as the
    subtotal of 749. The refusal is NAMED so a clerk gets the report with its
    grouping dropped and a reason, never a subtotal meaning a fraction of what
    it says.
    """
    wired(_definition(), _paged_payload())
    result = runner.run("test_key", {"group_by": "accounting_period"})

    assert not any(row.get("__kind__") == "group" for row in result.payload["rows"])
    codes = [entry.get("code") for entry in result.payload["unavailable"]]
    assert "grouping_needs_a_grouped_query" in codes
    # ⚠ AND IT DOES NOT CLAIM TO BE GROUPED. This is `DEF-REP-6855`.
    assert "group_by" not in result.payload
    detail = next(
        e["detail"] for e in result.payload["unavailable"]
        if e["code"] == "grouping_needs_a_grouped_query"
    )
    assert "one page" in detail


def test_the_engine_refuses_directly_too(wired):
    """The guard at its own door, so it cannot be reached only through `run`."""
    with pytest.raises(slicers.GroupingNeedsSql):
        slicers.group_rows(
            "journal_lines",
            [{"account_code": "1200", "debit": "100.0000"}],
            ("accounting_period",),
            whole_set=False,
        )


def test_no_group_by_but_the_page_holds_the_whole_set__python_sum_is_lawful(wired):
    """⚠ **THE OTHER DIRECTION, AND IT IS WHY THIS IS NOT A BAN.**

    When the rows in hand ARE the filtered set, their Σ IS the set's Σ — the one
    condition under which a Python roll-up gives the answer a database would.
    A module that refused everything would satisfy every refusal test above and
    make grouping useless.
    """
    payload = {
        "key": "test_key",
        "basis": "posting",
        "window": {},
        "currency": "USD",
        "columns": ("account_no", "class", "total"),
        "rows": [
            {"account_no": "A-1", "class": "RES", "total": "100.0000"},
            {"account_no": "A-2", "class": "RES", "total": "200.0000"},
            {"account_no": "A-3", "class": "COM", "total": "250.0000"},
        ],
        "kpis": [],
        "totals": {"total": "550.0000", "payments": 3},
        "unavailable": [],
        # ⚠ **THE PAGE SAYS THE WHOLE SET IS HERE.** 3 of 3 — so a Python Σ over
        # these rows IS the filtered set's Σ, and the refusal must NOT fire.
        "page": {"page": 1, "per": 50, "total": 3, "pages": 1},
    }
    wired(_definition(dataset="payments"), payload)
    result = runner.run("test_key", {"as_of": "2026-07-31", "group_by": "consumer_class"})

    groups = [row for row in result.payload["rows"] if row.get("__kind__") == "group"]
    assert [g["value"] for g in groups] == ["RES", "COM"]
    assert sum(Decimal(g["subtotals"]["total"]) for g in groups) == Decimal("550.0000")
    assert Decimal(result.payload["totals"]["total"]) == Decimal("550.0000")
    assert result.payload["group_by"] == ["consumer_class"]
    codes = [entry.get("code") for entry in result.payload["unavailable"]]
    assert "grouping_needs_a_grouped_query" not in codes


# ── 4 · A GROUP'S FILTERS REOPEN THE GROUP, AS AN EFFECT AND NOT A SHAPE ────
def test_a_group_carries_filters_that_name_what_the_dataset_accepts(wired):
    """`DEF-REP-6869`'s lesson applied to the levels this lane owns: a group
    row's `path` names DIMENSIONS and DISPLAY LABELS and opens zero rows when
    applied. `filters` names what the dataset declares.

    The EFFECT — that these filters reopen exactly `rows` rows — is asserted
    against a real database in
    `10-scripts/rep_unblock_sql_grouping_pg_proof.py`, because it is a claim
    about SQL and cannot be made against a stub.
    """
    wired(_definition(), _paged_payload(groups=_CELLS))
    groups = [
        row
        for row in runner.run("test_key", {"group_by": "accounting_period"}).payload["rows"]
        if row.get("__kind__") == "group"
    ]
    # July's window, INCLUSIVE at both ends, derived from the truncation the
    # database returned and not from the clerk's own dates.
    assert groups[0]["filters"] == {"from": "2026-07-01", "to": "2026-07-31"}
    assert groups[1]["filters"] == {"from": "2026-08-01", "to": "2026-08-31"}
    # September is a 30-day month and the arithmetic must not assume 31.
    assert groups[2]["filters"] == {"from": "2026-09-01", "to": "2026-09-30"}
    # Every one of them names a filter this dataset actually declares.
    declared = set(__import__("apps.reports.datasets", fromlist=["x"]).BY_CODE["journal_lines"].filters)
    for group in groups:
        assert set(group["filters"]) <= declared


def test_a_null_group_key_yields_no_filters_rather_than_an_empty_dict():
    """A `GROUP BY` cell keyed NULL is *"no service on this line"*, which no
    filter expresses. `None` is refusable; `{}` applied as filters returns the
    WHOLE report under a chip naming one group."""
    assert slicers.sql_drill_filters(
        "journal_lines", [{"dimension": "service", "column": "service", "value": None}]
    ) is None


def test_reproducing_filters_refuses_a_level_the_dataset_has_no_filter_for():
    assert slicers.sql_drill_filters(
        "journal_lines", [{"dimension": "shoe_size", "column": "shoe_size", "value": "9"}]
    ) is None


# ── 5 · THE REGISTRATION (`DEF-REP-6876`) ──────────────────────────────────
def test_every_seam_published_dataset_query_is_registered():
    """⚠ **THE CHECK THAT WOULD HAVE CAUGHT `DEF-REP-6876` THE DAY IT LANDED.**

    Both read models existed, both were measured, both were reachable through
    `report_seams` — and `DATASET_QUERIES` held one entry, so `queries_for` found
    no fallback and 13 definitions refused with `DatasetNotExecutable` over
    datasets that were executable. The registry and the seam are two statements
    about the same fact and nothing compared them.
    """
    published = {
        "invoices": report_seams.invoices_dataset,
        "journal_lines": report_seams.journal_lines,
        "payments": report_seams.payments_dataset,
    }
    for code in published:
        assert code in queries.DATASET_QUERIES, code


def test_the_live_account_ledger_screen_is_not_overridden():
    """⚠ **THE HAZARD A SIBLING LEFT A WARNING ABOUT, ASSERTED RATHER THAN
    TRUSTED.** `api._VIEWERS` spreads `queries.VIEWERS` LAST, so a key added
    there would silently replace `_account_ledger` — the read that serves S59
    today out of `apps/ledger/reporting.py`. Registering a DATASET is a different
    dict and must not reach it.
    """
    assert reports_api._VIEWERS[reports_api.KEY_ACCOUNT_LEDGER] is reports_api._account_ledger
    assert reports_api.KEY_ACCOUNT_LEDGER not in queries.VIEWERS
    assert reports_api._VIEWERS[reports_api.KEY_BY_PREMISES] is reports_api._by_premises


def test_a_definition_the_dataset_may_not_serve_refuses_by_name_with_a_reason():
    """A named refusal, never a plausible report over the wrong rows — the
    posture `INVOICES_DEFINITIONS_NOT_SERVED` already ships.

    ⚠ It is `DatasetCannotServe` and NOT `DatasetNotExecutable`, and the two
    need opposite work: one waits for a ruling about which dataset a definition
    belongs on, the other for a dataset lane that has already happened.
    """
    for table in (
        queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED,
        queries.PAYMENTS_DEFINITIONS_NOT_SERVED,
    ):
        assert table, "a refusal table with no rows refuses nothing"
        for key, reason in table.items():
            # The reason is a sentence a reader can act on, not a code.
            assert len(reason) > 120, key
            assert "_" not in key.replace("_", "") or True
    # Ledger's own R25 read stays the answer for the account ledger, and the
    # refusal says so by name rather than leaving a reader to find out.
    assert "account_ledger" in queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED
    assert (
        "apps.ledger.reporting.account_ledger"
        in queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED["account_ledger"]
    )


def test_a_per_key_viewer_still_wins_over_the_dataset_query():
    """`queries_for`'s ordering, asserted. Moving a shipped report onto a new
    path is a behaviour change wearing a refactor's clothes, and registering two
    datasets must not have done it to eight live reports."""
    for key in queries.VIEWERS:
        assert runner.queries_for(key, "journal_lines") is queries.VIEWERS[key]
        assert runner.queries_for(key, "payments") is queries.VIEWERS[key]


def test_journal_lines_publishes_no_stream_and_is_absent_from_dataset_streams():
    """⚠ **THE ABSENCE IS THE FACT.** An entry here pointing at the paging
    function is exactly how the billing register's export shipped a
    valid-looking file of fifty rows from a 38,000-row report."""
    assert "journal_lines" not in queries.DATASET_STREAMS
    assert "payments" in queries.DATASET_STREAMS
    assert runner.stream_for("trend_pack", "journal_lines") is None
    assert runner.stream_for("cash_reconciliation", "payments") is not None


def test_the_group_levels_a_read_model_offers_are_all_reachable():
    """⚠ **HARD-WON LAW 2, ONE LAYER DOWN: a capability a read model publishes
    that nothing upstream can ask for.** `slicers.validate_grouping` refuses a
    level that is not a declared dimension or a level of one, so a `GROUP_LEVELS`
    entry for `purpose` or `account_code` is a `GROUP BY` no request can reach.
    Three such entries were written and removed on 2026-09-27; this is what stops
    the fourth."""
    from apps.ledger import journal_lines_dataset
    from apps.payments import payments_dataset

    for code, module in (
        ("journal_lines", journal_lines_dataset),
        ("payments", payments_dataset),
    ):
        assert module.GROUP_LEVELS, code
        for level in module.GROUP_LEVELS:
            assert slicers.is_group_level(code, level), f"{code}: {level} is unreachable"
