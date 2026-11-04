# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.22 · P2.17 — the WIRING, not the engine.
# Rules:    CLAUDE.md hard-won law 2 (*"built is not wired"* — a component with
#           an optional prop that nothing passes is dead UI) · law 7 (*"ask
#           what would make this check pass wrongly"*)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""THE FOOTER REFUSAL IS ON THE PATH THE VIEWER AND THE EXPORT BOTH TAKE.

⚠ **WHY THIS FILE EXISTS BESIDE `test_rep_p2_22_unlawful_total.py`.** That file
proves the ENGINE: given a dataset, a measure and a direction, `additivity`
returns the right answer. It would pass in full with `additivity.py` sitting in
the repository imported by nothing — which is hard-won law 2 exactly, and four
defects in one day.

This file proves the funnel. `runner.run()` is the ONE path `apps/reports/api.py`
and `apps/reports/exports.py` both take (`P0.5`), so a refusal applied there
reaches the screen and the file together. `resolve` and `queries_for` are
substituted so the assertion is about the RUNNER and needs no database — the
alternative is 133 seconds of migration to prove a function is called.

⚠ **AND IT ASSERTS THE OTHER DIRECTION, WHICH IS THE HALF THAT COSTS MORE.**
The 39 shipped report tests passed after the wiring landed. That is only
evidence of *no regression* if the wiring is actually reached — an
`if False:` would have passed them too. So the last case here runs the same
report with no grouping and asserts the total is still a NUMBER.
"""

import pytest

from apps.reports import additivity, runner


def _definition(**over):
    base = dict(
        key="test_key",
        name="Test",
        dataset="payments",
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


def _stub_payload():
    return {
        "key": "test_key",
        "basis": "posting",
        "window": {},
        "currency": "USD",
        "columns": ("account_no", "class", "total"),
        "rows": [
            {"account_no": "A-1", "class": "RES", "total": "100.0000"},
            {"account_no": "A-2", "class": "RES", "total": "48121.1400"},
            {"account_no": "A-3", "class": "COM", "total": "250.0000"},
        ],
        "kpis": [],
        "totals": {"total": "48471.1400", "payments": 3},
        "unavailable": [],
    }


@pytest.fixture
def wired(monkeypatch):
    def install(definition):
        monkeypatch.setattr(runner, "resolve", lambda key: definition)
        monkeypatch.setattr(
            runner, "queries_for", lambda key, dataset=None: (lambda bound: _stub_payload())
        )
    return install


def test_p2_22__a_report_grouped_across_time_refuses_its_total_through_run(wired):
    """The outcome row, on the real path: *"AR Ageing grouped by month refuses
    its balance total and says why."*"""
    wired(_definition(group_by=("accounting_period",), filters={"from": "2026-07-01"}))
    result = runner.run("test_key", {"from": "2026-07-01"})
    total = result.payload["totals"]["total"]
    assert total["refused"] is True
    assert total["value"] is None
    assert total["display"] == additivity.EM_DASH
    assert total["reason"] == "Balances do not sum across time"
    assert "48471" not in repr(result.payload["totals"]["total"])


def test_p2_22__the_same_report_ungrouped_still_serves_a_number(wired):
    """⚠ **THE PAIR THE PO ASKED TO SEE, AND THE CHECK THAT STOPS THIS BEING A
    BAN.** As at a date, one row per debtor, no grouping — the balance total
    is exactly what a balance is for, and it must remain a figure."""
    wired(_definition(filters={"as_of": "2026-07-31"}))
    result = runner.run("test_key", {"as_of": "2026-07-31"})
    assert result.payload["totals"]["total"] == "48471.1400"
    assert result.payload["totals"]["payments"] == 3


def test_p2_17__grouping_inserts_subtotal_rows_through_run(wired):
    """`P2.17`'s group rows, on the real path — what `P2.24` opens and what
    `P2.18` drills through."""
    wired(_definition(group_by=("consumer_class",)))
    result = runner.run("test_key", {})
    groups = [row for row in result.payload["rows"] if row.get("__kind__") == "group"]
    # ⚠ The dimension is `consumer_class`; the served COLUMN is `class`. The
    # two are different names and nothing bridged them until `DEF-REP-6847` —
    # `_row_key` is that bridge, and this is it working on the real path.
    assert [g["value"] for g in groups] == ["RES", "COM"]
    assert groups[0]["path"][0]["column"] == "class"
    assert groups[0]["rows"] == 2
    # ⚠ The class subtotal spans NO time (the report is not grouped by time),
    # so it is a lawful number and must render as one.
    assert groups[0]["subtotals"]["total"] == "48221.1400"
    assert result.payload["group_by"] == ["consumer_class"]


def test_p2_17__a_grouping_the_dataset_cannot_serve_is_dropped_and_recorded(wired):
    """`bind`'s settled behaviour: a stale bookmark gets its report, not an
    error page — and what went is never silent."""
    wired(_definition(group_by=("shoe_size",)))
    result = runner.run("test_key", {})
    codes = [entry.get("code") for entry in result.payload["unavailable"]]
    assert "grouping_not_served" in codes
    assert not any(row.get("__kind__") == "group" for row in result.payload["rows"])


def test_p2_25__a_mixed_calendar_is_refused_at_save_by_validate(wired):
    """`P2.25` at the wall it belongs at. `validate()` is what `P5.2` calls on
    **Save as**; the render path drops instead, above."""
    from apps.reports import slicers

    with pytest.raises(slicers.CalendarMixed):
        runner.validate(
            _definition(dataset="invoices", group_by=("cycle",), filters={"period": "2026-07"})
        )


def test_p2_22__a_report_that_groups_by_nothing_is_byte_identical_to_before(wired):
    """The safety property the wiring rests on: `footer()` replaces a key only
    when there is something to refuse, so every shipped report is untouched."""
    wired(_definition(filters={"as_of": "2026-07-31"}))
    served = runner.run("test_key", {"as_of": "2026-07-31"}).payload["totals"]
    assert served == _stub_payload()["totals"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.22 · P2.17 · P2.25
# generated: 2026-09-27 by lane REP-P2-MODEL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
