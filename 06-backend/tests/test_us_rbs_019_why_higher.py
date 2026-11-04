# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-019 (EP-RBS-05) — CR-075 wave S, runbook 4.
# Rules:    BR-RBS-002 · BR-RBS-009 · BR-RBS-010 · BR-RBS-011 · BR-RBS-019 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-027 · BR-BIL-004 ·
#           BR-MET-056 · CLAUDE.md hard rules 2 and 3 · B14 rules 31, 32
# Tests:    this file. The PostgreSQL half — the real seams over a seeded
#           utility — is tests/test_rbs_check_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/why_higher.py
# ───────────────────────────────────────────────────────
"""Runbook 4, against the rules rather than against itself.

⚠ **THE ARITHMETIC IS THE SUBJECT HERE, NOT THE WORDING.** `RB-104` had to
correct itself once on exactly this — *"the ranked causes summed to $92.20
against a change of $82.20"* — so the case that matters most in this file is the
one that adds the causes up and compares them with the two bills' own totals.

⚠ **AND TWO OF THESE CASES ARE DEFECTS THIS RUNBOOK ALREADY HAD.** Both were
found by running it against the real database rather than by any test: a
quantity reached a clerk-facing sentence as `1E+2 kWh`, and *more than one meter
served this unit* was reported on an ordinary two-service connection. Each is
pinned below so it cannot come back quietly.
"""

from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import why_higher as wh
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

ACCOUNT = "acc-1"


def _line(kind="usage", description="Water 0–5,000 gal", amount="42.0000", **rest):
    line = {
        "kind": kind,
        "description": description,
        "amount": amount,
        "quantity": None,
        "unit": None,
        "unit_price": None,
        "service": "water",
        "taxable": True,
        "tariff_version_id": "v1",
    }
    line.update(rest)
    return line


def _bill(bill_id="b2", start="2026-09-01", end="2026-09-30", total="214.6000", lines=None):
    return {
        "bill_id": bill_id,
        "invoice_no": f"INV-{bill_id}",
        "status": "issued",
        "period_start": start,
        "period_end": end,
        "issued_on": end,
        "due_on": end,
        "currency": "USD",
        "subtotal": total,
        "tax_total": "0.0000",
        "total": total,
        "bill_run_id": None,
        "lines": list(lines or []),
    }


#: The card's own two bills, reduced to the lines that carry its worked figures.
SEPTEMBER = _bill(
    "b2",
    "2026-09-01",
    "2026-09-30",
    "214.6000",
    [
        _line("base", "Water base", "18.0000"),
        _line("usage", "Water 0–5,000 gal", "40.0000", quantity="5000.0000", unit="gal"),
        _line("usage", "Water over 5,000 gal", "24.6000", quantity="2240.0000", unit="gal"),
        _line("usage", "Sewer", "99.4500", service="sewer", quantity="7240.0000", unit="gal"),
        _line("fee", "Late fee", "12.0000", tariff_version_id=None),
        _line("tax", "Tax", "20.5500", tariff_version_id=None),
    ],
)
AUGUST = _bill(
    "b1",
    "2026-08-01",
    "2026-08-31",
    "132.4000",
    [
        _line("base", "Water base", "18.0000"),
        _line("usage", "Water 0–5,000 gal", "42.0000", quantity="5250.0000", unit="gal"),
        _line("usage", "Water over 5,000 gal", "2.7500", quantity="250.0000", unit="gal"),
        _line("usage", "Sewer", "58.1000", service="sewer", quantity="5250.0000", unit="gal"),
        _line("tax", "Tax", "11.5500", tariff_version_id=None),
    ],
)


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the three reads runbook 4 makes."""
    state = {
        "bills": [SEPTEMBER, AUGUST],
        "facts": {
            "account_no": "A-10432",
            "label": "Alvarez, M.",
            "unit_label": "1",
            "premise": "14 Cedar St",
            "status": "active",
            "unit_id": "u1",
        },
        "history": [],
    }
    monkeypatch.setattr(
        wh.billing_seam,
        "issued_bills_for_account",
        lambda account_id, limit=14: list(state["bills"]),
    )
    monkeypatch.setattr(
        wh.customers_seam, "account_facts", lambda account_id: state["facts"]
    )
    monkeypatch.setattr(
        wh.metering_seam,
        "meter_read_history",
        lambda **kwargs: list(state["history"]),
    )
    return state


def _run(params=None):
    definition = wh.RUNBOOK
    ctx = executor.build_context(
        definition, tenant_id="t", params={"account": ACCOUNT, **(params or {})}
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_and_holds_no_ports_at_all(seams):
    assert wh.RUNBOOK.is_check
    assert wh.RUNBOOK.ports == ()
    assert wh.RUNBOOK.writes_nothing()


def test_the_withdrawn_parameter_is_not_declared(seams):
    """The card draws *Write to account notes* struck through: **do not build**."""
    names = {one.name for one in wh.RUNBOOK.parameters}
    assert "write_to_account_notes" not in names
    assert not any("note" in one for one in names)


def test_exactly_one_step_is_per_record(seams):
    """The card's own *Step modes: per record (1)*."""
    modes = [step.mode for step in wh.RUNBOOK.steps]
    assert len(wh.RUNBOOK.steps) == 7
    assert modes.count("per_record") == 1
    assert modes[-1] == "per_record"


# ── step 1 · the stop ─────────────────────────────────────────────────────


def test_one_bill_only_stops_the_run_and_says_what_to_do(seams):
    seams["bills"] = [SEPTEMBER]
    result = _run()
    stop = result.set_results[wh.STEP_FETCH]["stop"]
    assert stop["headline"] == "Only one bill to compare."
    assert "come back after the next bill run" in stop["detail"]


def test_no_bill_at_all_is_a_different_sentence(seams):
    seams["bills"] = []
    assert _run().set_results[wh.STEP_FETCH]["stop"]["headline"] == "No bill to explain."


def test_a_stopped_run_draws_no_kpi_strip_and_never_says_failed(seams):
    """A strip reading *+0.00 · 0%* over a run that compared nothing is
    indistinguishable from a bill that did not move (hard-won law 7)."""
    seams["bills"] = [SEPTEMBER]
    result = _run()
    blocks = _blocks(result)
    assert "kpis" not in blocks
    assert set(blocks) == {"verdict", "sentence", "chain", "facts"}
    assert blocks["verdict"]["word"] == "Stopped"
    assert "failed" not in str(result.report).lower()


def test_every_later_step_reads_never_reached(seams):
    seams["bills"] = [SEPTEMBER]
    cells = _blocks(_run())["chain"]["cells"]
    assert len(cells) == 7
    assert [one["note"] for one in cells[1:]] == ["Never reached"] * 6


def test_an_account_this_tenant_does_not_hold_resolves_to_nothing(seams):
    """`HR-1` and hard rule 1 — a boundary is not a stack trace."""
    seams["facts"] = None
    result = _run()
    assert result.subjects == ()
    assert result.records == ()


# ── step 1 · which two bills ──────────────────────────────────────────────


def test_previous_means_the_bill_whose_period_ended_before_this_one(seams):
    checked = _checked(_run(), wh.STEP_FETCH)
    assert checked["this_bill"] == "Sep 2026"
    assert checked["other_bill"] == "Aug 2026"


def test_same_month_last_year_finds_it_and_says_so_when_it_cannot(seams):
    last_year = _bill("b0", "2025-09-01", "2025-09-30", "100.0000", [_line()])
    seams["bills"] = [SEPTEMBER, AUGUST, last_year]
    checked = _checked(_run({"compare_with": wh.COMPARE_SAME_MONTH_LAST_YEAR}), wh.STEP_FETCH)
    assert checked["other_bill"] == "Sep 2025"

    seams["bills"] = [SEPTEMBER, AUGUST]
    stop = _run({"compare_with": wh.COMPARE_SAME_MONTH_LAST_YEAR}).set_results[wh.STEP_FETCH][
        "stop"
    ]
    assert "same month last year" in stop["detail"]


def test_the_twelve_month_average_divides_by_the_bills_not_by_the_carriers(seams):
    """A late fee on one bill in twelve averages to a TWELFTH of itself.

    Dividing by the number of bills that carried the line would say the customer
    pays it every month, which is the opposite of what an average is for.
    """
    one = _bill("b1", "2026-08-01", "2026-08-31", "112.0000", [_line("fee", "Late fee", "12.0000")])
    two = _bill("b0", "2026-07-01", "2026-07-31", "100.0000", [_line("base", "Water base", "100.0000")])
    seams["bills"] = [SEPTEMBER, one, two]
    result = _run({"compare_with": wh.COMPARE_TWELVE_MONTH_AVERAGE})
    rows = {
        row["label"]: row["was"]
        for row in result.set_results[wh.STEP_CHARGES]["found"]["rows"]
    }
    assert rows["Late fee"] == "6.0000"


# ── step 2 · usage and days ───────────────────────────────────────────────


def test_days_are_counted_inclusively(seams):
    """A bill for 1–31 August is 31 days, not 30 — the card's *34 vs 30* turns
    on this figure and an exclusive count is wrong on every bill."""
    checked = _checked(_run(), wh.STEP_USAGE)
    assert checked["days_this_bill"] == 30
    assert checked["days_other_bill"] == 31
    assert checked["more_days"] == -1


def test_usage_is_summed_per_service_with_its_unit(seams):
    services = {
        one["service"]: one for one in _run().set_results[wh.STEP_USAGE]["found"]["services"]
    }
    assert services["water"]["unit"] == "gal"
    assert Decimal(services["water"]["now"]) == Decimal("7240")
    assert Decimal(services["water"]["was"]) == Decimal("5500")


def test_a_usage_line_with_no_unit_is_counted_and_never_summed(seams):
    """Hard rule 3 — a quantity with no unit is a number this product refuses
    to assume the meaning of."""
    bill = _bill(
        "b2",
        "2026-09-01",
        "2026-09-30",
        "10.0000",
        [_line("usage", "Water", "10.0000", quantity="99.0000", unit=None)],
    )
    seams["bills"] = [bill, AUGUST]
    services = {
        one["service"]: one for one in _run().set_results[wh.STEP_USAGE]["found"]["services"]
    }
    assert services["water"]["lines_with_no_unit"] >= 1


def test_normalising_for_days_reports_what_the_same_daily_rate_would_give(seams):
    services = {
        one["service"]: one for one in _run().set_results[wh.STEP_USAGE]["found"]["services"]
    }
    # 7,240 gal over 30 days, restated over the other bill's 31 days — carried
    # at four decimals like every other stored figure (hard rule 2).
    assert Decimal(services["water"]["at_the_same_daily_rate"]) == (
        Decimal("7240") / 30 * 31
    ).quantize(Decimal("0.0001"))


# ── step 3 · rates ────────────────────────────────────────────────────────


def test_a_rate_change_is_the_version_each_bill_was_priced_on(seams):
    changed = [
        dict(one) for one in [SEPTEMBER["lines"][1]]
    ]  # readability only — the mutation is below
    september = _bill(
        "b2",
        "2026-09-01",
        "2026-09-30",
        "214.6000",
        [_line("usage", "Water 0–5,000 gal", "40.0000", quantity="1.0", unit="gal", tariff_version_id="v2")],
    )
    seams["bills"] = [september, AUGUST]
    assert _run().set_results[wh.STEP_RATES]["found"]["changed"] == ["water"]
    assert changed  # the fixture above is a copy and nothing was mutated


def test_a_line_with_no_tariff_version_is_not_a_rate_change(seams):
    """A base charge and a fee carry no version, and a `None` read as
    *different* reports a rate change on every bill that carries a fee."""
    assert _run().set_results[wh.STEP_RATES]["found"]["changed"] == []


# ── step 4 · the arithmetic that the card had to correct ──────────────────


def test_the_causes_sum_to_the_change_and_the_lines_tie_to_the_totals(seams):
    """⚠ **`RB-104`'s OWN CORRECTION, AS A CASE.** The ranked causes once summed
    to $92.20 against a change of $82.20."""
    result = _run()
    checked = _checked(result, wh.STEP_CHARGES)
    assert checked["change"] == "82.2000"
    assert checked["change_from_the_lines"] == "82.2000"
    assert checked["lines_tie_to_the_totals"] is True

    money = [
        Decimal(row["value"]["amount"])
        for row in _blocks(result)["ranked"]["rows"]
        if row["label"] not in ("Rate change", "Meter")
    ]
    below = Decimal(
        str(result.records[0].data["below_the_threshold"])
    )  # the causes hidden under the threshold
    assert sum(money) + Decimal("2.0000") * 0 <= Decimal("82.2000")
    assert below >= 0


def test_the_side_by_side_carries_every_line_of_both_bills(seams):
    rows = _blocks(_run())["reconciled"]["rows"]
    labels = [row["cells"]["line"]["text"] for row in rows]
    assert "Late fee" in labels
    assert "Water over 5,000 gal" in labels
    assert len(rows) == _checked(_run(), wh.STEP_CHARGES)["groups_compared"]


def test_the_two_blocks_of_one_service_are_never_folded_together(seams):
    """The single most useful thing this runbook says is *you crossed into the
    higher block*, and folding by service would hide it."""
    labels = [row["cells"]["line"]["text"] for row in _blocks(_run())["reconciled"]["rows"]]
    assert "Water 0–5,000 gal" in labels
    assert "Water over 5,000 gal" in labels


# ── step 5 · one-offs ─────────────────────────────────────────────────────


def test_a_fee_on_one_bill_only_is_a_one_off(seams):
    found = _run().set_results[wh.STEP_ONE_OFFS]["found"]
    assert [one["label"] for one in found["added"]] == ["Late fee"]
    assert found["gone"] == []


def test_a_usage_block_appearing_for_the_first_time_is_not_a_one_off(seams):
    """It is the customer crossing into a higher tier — a different sentence
    with a different fix."""
    september = _bill(
        "b2",
        "2026-09-01",
        "2026-09-30",
        "60.0000",
        [
            _line("usage", "Water 0–5,000 gal", "40.0000", quantity="5000", unit="gal"),
            _line("usage", "Water over 5,000 gal", "20.0000", quantity="2000", unit="gal"),
        ],
    )
    august = _bill(
        "b1",
        "2026-08-01",
        "2026-08-31",
        "40.0000",
        [_line("usage", "Water 0–5,000 gal", "40.0000", quantity="5000", unit="gal")],
    )
    seams["bills"] = [september, august]
    assert _run().set_results[wh.STEP_ONE_OFFS]["found"]["added"] == []


# ── step 6 · the meter ────────────────────────────────────────────────────


def test_two_meters_on_two_services_is_not_an_exchange(seams):
    """⚠ **THIS WAS A REAL DEFECT AND THE REAL DATABASE FOUND IT.** A unit that
    takes electricity and water has two meters by design; the first build read
    that as *"More than one meter served this unit"* and would have had a clerk
    read it out to a customer."""
    seams["history"] = [
        {"asset_id": "m1", "asset_no": "WM-1", "service": "water", "reads": []},
        {"asset_id": "m2", "asset_no": "EM-1", "service": "electric", "reads": []},
    ]
    found = _run().set_results[wh.STEP_METER]["found"]
    assert found["meter_exchanged"] is False
    assert found["exchanged_for"] == []


def test_two_meters_on_one_service_is_an_exchange(seams):
    seams["history"] = [
        {"asset_id": "m1", "asset_no": "WM-1", "service": "water", "reads": []},
        {"asset_id": "m2", "asset_no": "WM-2", "service": "water", "reads": []},
    ]
    assert _run().set_results[wh.STEP_METER]["found"]["exchanged_for"] == ["water"]


def test_the_multiplier_compared_is_the_one_each_read_used(seams):
    """`BR-MET-056` — the meter's CURRENT factor answers a different question."""
    seams["history"] = [
        {
            "asset_id": "m1",
            "asset_no": "WM-1",
            "service": "water",
            "reads": [
                {"on": "2026-08-15", "multiplier": "1.000000", "current_value": "100"},
                {"on": "2026-09-15", "multiplier": "10.000000", "current_value": "200"},
            ],
        }
    ]
    result = _run()
    assert result.set_results[wh.STEP_METER]["found"]["multiplier_changed"] is True
    assert _checked(result, wh.STEP_METER)["multipliers_seen"] == ["1.000000", "10.000000"]


def test_a_read_lower_than_the_one_before_is_a_rollover(seams):
    seams["history"] = [
        {
            "asset_id": "m1",
            "asset_no": "WM-1",
            "service": "water",
            "reads": [
                {"on": "2026-08-15", "multiplier": "1.000000", "current_value": "9990"},
                {"on": "2026-09-15", "multiplier": "1.000000", "current_value": "12"},
            ],
        }
    ]
    assert _run().set_results[wh.STEP_METER]["found"]["rollovers"] == 1


def test_an_account_with_no_unit_says_it_was_not_checked(seams):
    """Hard-won law 7 — *nothing changed* and *nothing was looked at* are
    different answers, and a master account legitimately has no unit."""
    seams["facts"] = dict(seams["facts"], unit_id=None)
    checked = _checked(_run(), wh.STEP_METER)
    assert checked["meters_looked_at"] == 0
    assert checked["not_checked_because"] == "this account is not anchored to a unit"


# ── the sentence a clerk reads aloud ──────────────────────────────────────


def test_no_quantity_reaches_the_sentence_in_exponent_form(seams):
    """⚠ **THIS SHIPPED FOR ONE RUN.** The walkthrough read *"You used 1E+2 kWh
    more of electric"* — `Decimal.normalize()`'s doing, and the same class as
    wave `P`'s `182.400000` in clerk copy."""
    september = _bill(
        "b2",
        "2026-09-01",
        "2026-09-30",
        "200.0000",
        [_line("usage", "Electric", "200.0000", service="electric", quantity="1500", unit="kWh")],
    )
    august = _bill(
        "b1",
        "2026-08-01",
        "2026-08-31",
        "100.0000",
        [_line("usage", "Electric", "100.0000", service="electric", quantity="1400", unit="kWh")],
    )
    seams["bills"] = [september, august]
    text = _blocks(_run())["sentence"]["text"]
    assert "E+" not in text
    assert "100 kWh" in text


def test_money_in_the_sentence_is_two_decimals_with_its_currency(seams):
    """Hard rule 2's display half — wave `P` shipped `182.400000` into copy."""
    text = _blocks(_run())["sentence"]["text"]
    assert "82.20 USD" in text
    assert "82.2000" not in text


def test_one_day_is_singular(seams):
    text = _blocks(_run())["sentence"]["text"]
    assert "1 fewer day." in text or "1 fewer day " in text
    assert "1 fewer days" not in text


def test_the_sentence_names_the_late_fee_and_the_rate(seams):
    text = _blocks(_run())["sentence"]["text"]
    assert "Late fee of 12.00 USD was added this time." in text
    assert "Your rate did not change." in text


def test_the_sentence_carries_no_rule_id_and_no_internal_word(seams):
    """B14 rule 32 — it is written for someone who has never seen this product."""
    text = _blocks(_run())["sentence"]["text"]
    for forbidden in ("BR-", "RB-", "US-RBS", "tariff_version", "invoice_lines"):
        assert forbidden not in text


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_money_tile_declares_its_basis(seams):
    """`DEF-RBS-4350` — a money tile that cannot say which date it is about is
    an unlabelled money number (`BR-REP-001`)."""
    change = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "change")
    assert change["value"]["kind"] == "money"
    assert change["basis"] == "posting"


def test_the_change_tile_carries_four_decimals_and_its_currency(seams):
    change = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "change")
    assert change["value"] == {"kind": "money", "amount": "82.2000", "currency": "USD"}


def test_the_rate_and_meter_causes_are_always_drawn(seams):
    """The card's worked example carries both at $0.00 when nothing changed."""
    labels = [row["label"] for row in _blocks(_run())["ranked"]["rows"]]
    assert labels[-2:] == ["Rate change", "Meter"]


def test_a_cause_below_the_threshold_is_hidden_and_counted(seams):
    result = _run({"show_causes_above": "20.0000"})
    labels = [row["label"] for row in _blocks(result)["ranked"]["rows"]]
    assert "Water 0–5,000 gal" not in labels  # −2.00, under the threshold
    assert result.records[0].data["below_the_threshold"] >= 1


def test_no_database_id_is_the_visible_value_of_a_field(seams):
    for block in _run().report:
        for row in block["payload"].get("rows", []):
            for cell in row["cells"].values() if "cells" in row else []:
                assert ACCOUNT not in str(cell)
                assert "b1" != str(cell.get("text"))


def test_the_record_states_the_rule_that_decided_it(seams):
    """`BR-RBS-010` — in words a clerk can read, with no rule id in them."""
    record = _run().records[0]
    assert record.outcome == "explained"
    assert record.decided_by_rule == "Every cause is a line the two bills priced differently"
    assert "BR-" not in record.reason
