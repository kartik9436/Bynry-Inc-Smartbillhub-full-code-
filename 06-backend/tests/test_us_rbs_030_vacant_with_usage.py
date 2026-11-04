# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-030 (EP-RBS-05) — CR-075 wave S, runbook 18.
# Rules:    BR-RBS-002 · BR-RBS-012 · BR-RBS-019 · BR-RBS-020 · BR-RBS-021 ·
#           BR-RBS-035 · BR-CUS-070 · CLAUDE.md hard rules 2, 3 and 8 ·
#           B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half is tests/test_rbs_check_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/vacant_with_usage.py
# ───────────────────────────────────────────────────────
"""Runbook 18, against the rules rather than against itself.

⚠ **THE SEEDED UTILITY PRODUCES ONLY ONE OF THE FOUR CAUSES.** Its five
non-sample premises with a meter have never had an account, so every finding
there is *Construction*; an unbilled occupant, a leak and a stopped meter all
need a closed account with a history behind it, and those live here. The real
run's figures are in the lane report and neither number is quoted alone.
"""

import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import vacant_with_usage as vw
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)


def _premises(premises_id="p1", label="22 Harbor Rd", is_sample=False, meters=1, units=("u1",)):
    return {
        "premises_id": premises_id,
        "label": label,
        "address_line": label,
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "is_sample": is_sample,
        "unit_ids": list(units),
        "unit_labels": {one: "1" for one in units},
        "service_points": [{"id": "sp1", "unit_id": units[0], "service": "water"}],
        "meters": [
            {"asset_id": f"a{index}", "asset_no": f"WM-{index}", "category": "meters"}
            for index in range(meters)
        ],
    }


def _read(on, consumption, unit="gal"):
    return {
        "read_id": f"r-{on}",
        "on": on,
        "channel": "total",
        "consumption": None if consumption is None else str(consumption),
        "current_value": "1000",
        "multiplier": "1.000000",
        "unit": unit,
        "estimated": False,
        "account_id": None,
        "is_sample": False,
    }


def _meter(premises_id="p1", asset_no="WM-0", reads=None):
    return {
        "asset_id": f"m-{premises_id}",
        "asset_no": asset_no,
        "service": "water",
        "unit_id": "u1",
        "premises_id": premises_id,
        "is_sample": False,
        "reads": list(reads or []),
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the six reads runbook 18 makes.

    The default is ONE vacant premises using 41,200 gal, whose last account
    closed on 3 June having used the same sort of volume — the card's own first
    row.
    """
    state = {
        "premises": [_premises()],
        # ⚠ **THE FIXTURE HONOURS `since`, AND IT HAS TO.** The runbook makes TWO
        # reads of different lengths — the window, and the whole history the
        # occupied comparison needs — and a fixture that answered both with one
        # list would make *"what it used while occupied"* and *"what it is using
        # now"* the same number. Two of the four causes turn on their being
        # different, so a fixture that could not tell them apart is a fixture
        # that cannot tell a working build from a broken one (hard-won law 2's
        # 2026-09-05 note).
        "history": [
            _meter(
                reads=[
                    # occupied — before the account closed on 3 June
                    _read("2026-04-01", 10000),
                    _read("2026-05-01", 10000),
                    # vacant, inside the 90-day window
                    _read("2026-07-01", 20000),
                    _read("2026-08-01", 21200),
                ]
            )
        ],
        "occupied": {},
        "last_closed": {
            "u1": {
                "id": "acc-old",
                "account_no": "A-1",
                "label": "Okonkwo, D.",
                "closed_on": "2026-06-03",
            }
        },
        "pending": {"_applications_not_resolved_to_a_premises": [{"count": 0}]},
        "bills": [
            {
                "bill_id": "b1",
                "period_end": "2026-06-30",
                "currency": "USD",
                "lines": [
                    {
                        "kind": "usage",
                        "service": "water",
                        "amount": "100.0000",
                        "quantity": "10000.0000",
                        "unit": "gal",
                        "description": "Water",
                    }
                ],
            }
        ],
        "currency": "USD",
    }
    monkeypatch.setattr(
        vw.metering_seam,
        "premises_meter_census",
        lambda *, include_sample=True: {
            "premises": list(state["premises"]),
            "meters_answered": True,
            "meters_without_a_service_point": [],
        },
    )
    def _history(**kwargs):
        since = kwargs.get("since")
        out = []
        for meter in state["history"]:
            reads = [
                one
                for one in meter["reads"]
                if since is None or str(one["on"]) >= since.isoformat()
            ]
            out.append(dict(meter, reads=reads))
        return out

    monkeypatch.setattr(vw.metering_seam, "meter_read_history", _history)
    monkeypatch.setattr(
        vw.customers_seam, "accounts_for_units", lambda unit_ids: dict(state["occupied"])
    )
    monkeypatch.setattr(
        vw.customers_seam,
        "last_closed_account_for_units",
        lambda unit_ids: dict(state["last_closed"]),
    )
    monkeypatch.setattr(vw.customers_seam, "pending_move_ins", lambda: dict(state["pending"]))
    monkeypatch.setattr(
        vw.billing_seam,
        "issued_bills_for_account",
        lambda account_id, limit=14: list(state["bills"]),
    )
    monkeypatch.setattr(vw.tenancy_seam, "today", lambda: TODAY)
    monkeypatch.setattr(vw.tenancy_seam, "currency", lambda: state["currency"])
    return state


def _run(params=None):
    definition = vw.RUNBOOK
    ctx = executor.build_context(
        definition,
        tenant_id="t",
        params={
            "service": "water",
            "window_days": 90,
            "usage_means_more_than": 500,
            "stopped_means": 3,
            **(params or {}),
        },
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_over_premises(seams):
    assert vw.RUNBOOK.is_check
    assert vw.RUNBOOK.ports == ()
    assert vw.RUNBOOK.subject_type == "premise"
    assert len(vw.RUNBOOK.steps) == 6
    assert [one.mode for one in vw.RUNBOOK.steps].count("per_record") == 1


def test_a_premises_with_no_meter_is_not_in_scope(seams):
    """The card's scope row is *Premises: All with a meter*."""
    seams["premises"] = [_premises("p1"), _premises("p2", meters=0)]
    assert {one.subject_id for one in _run().subjects} == {"p1"}


def test_a_sample_premises_is_guarded_counted_and_seen_by_no_step(seams):
    seams["premises"] = [_premises("p1"), _premises("p2", is_sample=True)]
    result = _run()
    assert len(result.subjects) == 2
    assert [one.subject_id for one in result.guarded] == ["p2"]
    assert result.counts[executor.OUTCOME_SKIPPED] == 1


# ── the two halves ────────────────────────────────────────────────────────


def test_a_vacant_premises_using_water_is_a_finding(seams):
    result = _run()
    assert _checked(result, vw.STEP_VACANT)["vacant_with_a_meter"] == 1
    assert _checked(result, vw.STEP_USAGE)["vacant_and_using"] == 1
    assert result.records[0].outcome == vw.CAUSE_OCCUPANT


def test_an_occupied_premises_is_not_vacant(seams):
    seams["occupied"] = {"u1": {"id": "acc-1", "account_no": "A-2", "status": "active"}}
    result = _run()
    assert _checked(result, vw.STEP_VACANT)["vacant_with_a_meter"] == 0
    assert _checked(result, vw.STEP_VACANT)["occupied_with_a_meter"] == 1


def test_an_occupied_meter_reading_zero_three_times_is_a_stopped_meter(seams):
    """The mirror half — *revenue being lost on an account that looks fine*."""
    seams["occupied"] = {"u1": {"id": "acc-1", "account_no": "A-2", "status": "active"}}
    seams["history"] = [
        _meter(reads=[_read("2026-06-15", 0), _read("2026-07-01", 0), _read("2026-08-01", 0)])
    ]
    result = _run()
    assert result.records[0].outcome == vw.CAUSE_STOPPED
    assert result.records[0].fix_route == "assets"
    assert "billed base only" in result.records[0].reason


def test_usage_below_the_threshold_is_not_a_finding(seams):
    seams["history"] = [_meter(reads=[_read("2026-07-01", 100), _read("2026-08-01", 100)])]
    assert _checked(_run(), vw.STEP_USAGE)["vacant_and_using"] == 0


def test_a_premises_with_no_reads_at_all_is_counted_not_judged(seams):
    """It is not vacant-with-usage and it is not evidence of anything."""
    seams["history"] = []
    assert _checked(_run(), vw.STEP_USAGE)["vacant_with_no_reads_at_all"] == 1


def test_an_unmeasured_period_is_never_added_in_as_zero(seams):
    """A `None` consumption is a read with no prior, not a month of nothing."""
    seams["history"] = [_meter(reads=[_read("2026-07-01", None), _read("2026-08-01", 41200)])]
    result = _run()
    using = (result.set_results[vw.STEP_USAGE]["found"] or {})["using"]["p1"]
    assert Decimal(using["used"]) == Decimal("41200")
    # and the gap is COUNTED rather than added in as a month of nothing
    assert using["periods_with_no_reading"] == 1


# ── the four causes ───────────────────────────────────────────────────────


def test_never_an_account_reads_construction(seams):
    seams["last_closed"] = {}
    result = _run()
    assert result.records[0].outcome == vw.CAUSE_CONSTRUCTION
    assert result.records[0].reason == "Construction. Nobody has ever had an account here."
    assert result.records[0].data["fix_label"] == "Bill the builder →"


def test_using_about_what_the_last_occupant_used_reads_occupant_unbilled(seams):
    """The comparison is the premises' OWN history, never a fleet average."""
    result = _run()
    assert result.records[0].outcome == vw.CAUSE_OCCUPANT
    assert "of what the last account used" in result.records[0].reason


def test_using_far_less_than_the_last_occupant_reads_possible_leak(seams):
    # 20,000 gal a month while occupied; 800 gal over the whole 90-day window.
    seams["history"] = [
        _meter(
            reads=[
                _read("2026-04-01", 10000),
                _read("2026-05-01", 10000),
                _read("2026-07-01", 400),
                _read("2026-08-01", 400),
            ]
        )
    ]
    result = _run()
    assert result.records[0].outcome == vw.CAUSE_LEAK
    assert result.records[0].data["fix_label"] == "Inspect →"


def test_with_no_occupied_history_the_row_says_so_rather_than_guessing(seams):
    """⚠ A guess presented as a measurement is worse than a guess that says
    what it is."""
    seams["last_closed"] = {
        "u1": {"id": "acc-old", "account_no": "A-1", "label": "Okonkwo, D.", "closed_on": None}
    }
    result = _run()
    assert result.records[0].outcome == vw.CAUSE_OCCUPANT
    assert result.records[0].reason.endswith("No earlier usage to compare.")


def test_a_pending_move_in_is_not_a_finding_and_is_counted(seams):
    """Closed OUT OF SCOPE by the card: *they are already somebody's job*."""
    seams["pending"] = {
        "p1": [{"request_no": "SR-26-0046", "state": "submitted", "outcome": "move_in"}],
        "_applications_not_resolved_to_a_premises": [{"count": 2}],
    }
    result = _run()
    assert result.records[0].outcome == vw.CAUSE_PENDING
    checked = _checked(result, vw.STEP_PENDING)
    assert checked["of_those_on_a_premises_this_run_found"] == 1
    assert checked["applications_not_resolved_to_a_premises"] == 2


# ── the money ─────────────────────────────────────────────────────────────


def test_the_estimate_is_the_usage_priced_at_what_the_last_occupant_paid(seams):
    """41,200 gal over 90 days at $0.01 a gallon = $412.00 over the window,
    which is $137.3333 a month."""
    result = _run()
    per_month = Decimal(result.records[0].data["per_month"])
    assert per_month == (Decimal("41200") * Decimal("0.01") / 90 * 30).quantize(
        Decimal("0.0001")
    )


def test_a_premises_whose_last_account_never_billed_reads_an_em_dash(seams):
    seams["bills"] = []
    result = _run()
    assert result.records[0].data["per_month"] is None
    row = _blocks(result)["records"]["rows"][0]["cells"]
    assert row["per_month"] == {"kind": "text", "text": "—"}


def test_the_money_tile_is_priced_and_says_how_many_could_not_be(seams):
    seams["bills"] = []
    tile = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "unbilled")
    assert tile["basis"] == "priced"
    assert tile["value"] == {"kind": "text", "text": "—"}
    assert "could not be priced" in tile["detail"]


def test_est_per_month_reads_an_em_dash_on_a_stopped_meter(seams):
    """`RB-118`'s own note: *Est. / month reads — on a stopped meter.*"""
    seams["occupied"] = {"u1": {"id": "acc-1", "account_no": "A-2", "status": "active"}}
    seams["history"] = [
        _meter(reads=[_read("2026-06-15", 0), _read("2026-07-01", 0), _read("2026-08-01", 0)])
    ]
    row = _blocks(_run())["records"]["rows"][0]["cells"]
    assert row["per_month"] == {"kind": "text", "text": "—"}


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_rows_are_ranked_by_estimated_revenue(seams):
    """The card: *the unbilled occupant is above the leak*."""
    seams["premises"] = [_premises("p1", "22 Harbor Rd"), _premises("p2", "9 Willow Ct", units=("u2",))]
    seams["history"] = [
        _meter("p1", reads=[_read("2026-07-01", 41200)]),
        dict(_meter("p2", reads=[_read("2026-07-01", 9400)]), unit_id="u2"),
    ]
    seams["last_closed"] = {}
    rows = _blocks(_run())["records"]["rows"]
    assert rows[0]["cells"]["premise"]["text"] == "22 Harbor Rd"


def test_the_used_cell_carries_its_unit(seams):
    """Hard rule 3 — a quantity never travels without one."""
    cell = _blocks(_run())["records"]["rows"][0]["cells"]["used"]
    assert cell["kind"] == "unit"
    assert cell["unit"] == "gal"


def test_no_database_id_and_no_cause_code_reaches_a_drawn_cell(seams):
    for row in _blocks(_run())["records"]["rows"]:
        drawn = " ".join(
            str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
        )
        assert "p1" != drawn
        assert "occupant_unbilled" not in drawn
        assert "BR-" not in drawn


def test_the_action_is_disabled_with_a_short_reason(seams):
    action = _blocks(_run())["action"]
    assert action["enabled"] is False
    assert len(action["reason"].split()) <= 7


def test_a_clean_estate_says_so(seams):
    seams["history"] = [_meter(reads=[_read("2026-07-01", 10)])]
    blocks = _blocks(_run())
    assert blocks["verdict"]["word"] == "Nothing found"
    assert blocks["records"]["empty"]["title"] == (
        "Nothing is being used where nobody is billed."
    )
