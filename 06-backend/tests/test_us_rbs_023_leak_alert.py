# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-023 (EP-RBS-05) — CR-075 wave R′, runbook 11.
# Rules:    BR-RBS-002 · BR-RBS-003 · BR-RBS-006 · BR-RBS-011 · BR-RBS-012 ·
#           BR-RBS-019 · BR-RBS-020 · BR-RBS-021 · BR-RBS-027 · BR-RBS-035 ·
#           BR-RBS-040 · BR-NOT-005 · RBR-15 · CLAUDE.md hard rule 3 ·
#           hard rule 8 · B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half — the real seams and the savepoint —
#           is tests/test_rbs_reads_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/leak_alert.py
# ───────────────────────────────────────────────────────
"""Runbook 11, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED, AND WHAT THAT DOES AND DOES NOT PROVE IS STATED.**
These cases hand the runbook fixed answers so the DECISIONS can be exercised — a
meter running continuously, one four times its own normal, one below the floor,
one whose unit does not match the floor's, one already told this week, one with
no channel, one on an empty property. **It proves the runbook's reasoning and
NOTHING about the seams**: a seam returning the wrong shape passes every case
here. `tests/test_rbs_reads_runbooks_pg.py` runs the REAL seams on real
PostgreSQL, and both numbers are quoted in the lane report — neither alone.
"""

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import leak_alert as leak
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

UTILITY = "Silver Creek Water"


def _day(
    meter_no="WM-04471",
    day="2026-09-06",
    *,
    asset_id=None,
    intervals=24,
    nonzero=None,
    quantity="1140",
    unit="gal",
    unit_conflict=False,
    unit_id=None,
    premises_id=None,
    sample=False,
):
    """One rolled-up meter-day, in the shape the seam hands across."""
    asset = asset_id or f"asset-{meter_no}"
    return {
        "asset_id": asset,
        "meter_no": meter_no,
        "channel": "total",
        "day": day,
        "intervals": intervals,
        "zero_intervals": intervals - (intervals if nonzero is None else nonzero),
        "nonzero_intervals": intervals if nonzero is None else nonzero,
        "quantity": quantity,
        "unit": unit,
        "unit_conflict": unit_conflict,
        "first_at": f"{day}T00:00:00",
        "last_at": f"{day}T23:00:00",
        "service": "water",
        "is_sample": sample,
        "unit_id": unit_id or f"unit-{meter_no}",
        "premises_id": premises_id or f"prem-{meter_no}",
    }


def _batch(days):
    return {
        "batch_id": "batch-11",
        "batch_no": "AMI-0091",
        "file_name": "ami-2026-09-06.csv",
        "status": "validated",
        "source_kind": "ami_replay",
        "source_detail": None,
        "service": "water",
        "intervals": sum(one["intervals"] for one in days),
        "intervals_unreadable": 0,
        "meters": len({one["asset_id"] for one in days}),
        "meter_days": list(days),
    }


def _normal(average="380", unit="gal"):
    return {
        "average_per_day": average,
        "unit": unit,
        "unit_conflict": False,
        "reads_seen": 90,
        "days_covered": 90,
        "last_good_day": "2026-09-05",
        "window_days": 90,
        "window_start": "2026-06-08",
        "window_end": "2026-09-06",
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for every read runbook 11 makes.

    Defaults to *nothing connected and nothing landed*, which is the STOP — so
    a case that forgets to give the runbook work cannot land on a happy path.
    Accounts, channels and addresses default to *present and reachable by text*,
    because the cases about their ABSENCE say so explicitly.
    """
    state = {
        "connections": [],
        "batch": None,
        "normals": {},
        "accounts": {},
        "channels": {},
        "premises": [],
        "disputed": set(),
        "told": {},
        "cap": None,
    }

    monkeypatch.setattr(
        leak.integrations_seam, "live_connections", lambda keys: list(state["connections"])
    )
    monkeypatch.setattr(leak.metering_seam, "interval_batch", lambda batch_id=None: state["batch"])
    monkeypatch.setattr(
        leak.metering_seam,
        "meter_normals",
        lambda ids, *, as_of, days=90: {
            one: state["normals"].get(one, _normal()) for one in ids
        },
    )
    monkeypatch.setattr(
        leak.metering_seam,
        "premises_for_reconciliation",
        lambda include_sample=False: list(state["premises"]),
    )
    monkeypatch.setattr(
        leak.metering_seam,
        "unit_has_dispute_hold",
        lambda unit_id: str(unit_id) in state["disputed"],
    )
    monkeypatch.setattr(
        leak.customers_seam,
        "accounts_for_units",
        lambda unit_ids: {
            str(one): state["accounts"].get(
                str(one),
                {"id": f"acct-{one}", "account_no": f"A-{one}", "customer_name": "Alvarez, M."},
            )
            for one in unit_ids
            if str(one) not in state.get("_no_account", ())
        },
    )
    monkeypatch.setattr(
        leak.customers_seam,
        "contact_channels_for",
        lambda ids: {
            str(one): state["channels"].get(str(one), {"email": True, "text": True, "post": True})
            for one in ids
        },
    )
    monkeypatch.setattr(leak, "_already_told_ids", lambda key, ids, days: dict(state["told"]))
    monkeypatch.setattr(leak, "_cap", lambda ctx: state["cap"])
    return state


def _address(meter_no, line="14 Cedar St"):
    return {"premises_id": f"prem-{meter_no}", "address_line": line}


def _run(seams, params=None):
    settings = {"utility_name": UTILITY}
    settings.update(params or {})
    definition = leak.RUNBOOK
    ctx = executor.build_context(definition, tenant_id="t", run_id=None, params=settings)
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


def _tiles(result):
    return {tile["id"]: tile for tile in _blocks(result)["kpis"]["tiles"]}


def _rows(result):
    return {
        row["cells"]["meter"]["text"]: row for row in _blocks(result)["records"]["rows"]
    }


# ── step 1 · the two doors, and the stop ──────────────────────────────────


def test_both_doors_shut_stops_the_run_and_names_both_absences(seams):
    """PO 2026-09-06: *"in absence of API conenctions … that is a valid case"*."""
    stop = (_run(seams).set_results[leak.STEP_GATHER])["stop"]
    assert stop["headline"] == "No interval data to read."
    assert "No meter connection is set up." in stop["detail"]
    assert "No intervals have landed either" in stop["detail"]


def test_a_stopped_run_draws_no_kpi_strip_and_never_says_failed(seams):
    """A strip of zeros over a run that examined nothing reads like a clean day."""
    result = _run(seams)
    blocks = _blocks(result)
    assert "kpis" not in blocks
    assert set(blocks) == {"verdict", "sentence", "chain", "records"}
    assert "failed" not in repr(result.report).lower()


def test_a_stopped_run_reads_never_reached_on_every_later_step(seams):
    """`BR-RBS-027`. A blank cell reads as *nothing wrong*; this one does not."""
    chain = _blocks(_run(seams))["chain"]
    assert [cell["state"] for cell in chain["cells"]] == [
        "bad", "notReached", "notReached", "notReached", "notReached", "notReached",
    ]


# ── BR-RBS-019 · one subject per METER, not per meter-day ─────────────────


def test_the_subject_is_the_meter_so_a_two_day_leak_is_one_alert(seams):
    """One customer, one text. A per-meter-day subject would text twice.

    That is exactly what *once per meter every 7 days* exists to prevent, and a
    guard cannot save you from a scope that was wrong to begin with.
    """
    seams["batch"] = _batch(
        [_day("WM-1", day="2026-09-05"), _day("WM-1", day="2026-09-06")]
    )
    seams["premises"] = [_address("WM-1")]
    result = _run(seams)
    assert leak.RUNBOOK.subject_type == "meter"
    assert len(result.subjects) == 1
    assert len(result.records) == 1


# ── step 3 · the two patterns, and the floor that has a unit in it ────────


def test_continuous_flow_is_found_and_the_text_names_the_hours(seams):
    """`RB-111`: *"water has been running at 14 Cedar St for 26 hours"*."""
    seams["batch"] = _batch([_day("WM-04471", intervals=48, nonzero=48, quantity="1140")])
    seams["premises"] = [_address("WM-04471")]
    result = _run(seams)
    assert _checked(result, leak.STEP_FLAG)["continuous_flow"] == 1
    sentence = _blocks(result)["sentence"]
    assert sentence["label"] == "What the customer receives"
    assert sentence["text"].startswith(f"{UTILITY}: water has been running at 14 Cedar St for ")
    assert sentence["text"].endswith("Reply STOP to opt out.")


def test_the_alert_text_never_names_the_account_or_a_dollar_figure(seams):
    """`RBR-15`. A customer can act on neither, and a figure at 07:30 is a bill
    nobody has issued."""
    seams["batch"] = _batch([_day("WM-04471", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-04471")]
    text = _blocks(_run(seams))["sentence"]["text"]
    assert "$" not in text
    assert "A-unit-" not in text
    assert "acct-" not in text


def test_a_spike_is_measured_against_this_meters_own_normal_never_a_fleet_one(seams):
    """S-1. A fleet average alerts on every large customer and no small one."""
    day = _day("WM-01128", intervals=24, nonzero=12, quantity="3900")
    seams["batch"] = _batch([day])
    seams["normals"] = {day["asset_id"]: _normal(average="928")}
    seams["premises"] = [_address("WM-01128", "Riverside Apts")]
    result = _run(seams)
    assert _checked(result, leak.STEP_FLAG)["far_above_own_normal"] == 1
    assert "4.2× normal" in _rows(result)["WM-01128"]["cells"]["pattern"]["text"]


def test_a_meter_with_no_normal_is_never_alerted_on_the_spike_rule(seams):
    """**No normal is not a normal of zero.** A zero makes every reading
    infinitely above normal and puts that on a customer's phone at 07:30."""
    day = _day("WM-NEW", intervals=24, nonzero=12, quantity="9999")
    seams["batch"] = _batch([day])
    seams["normals"] = {day["asset_id"]: _normal(average=None, unit=None)}
    seams["premises"] = [_address("WM-NEW")]
    result = _run(seams)
    assert _checked(result, leak.STEP_FLAG)["far_above_own_normal"] == 0
    assert _checked(result, leak.STEP_NORMAL)["meters_with_no_normal"] == 1


def test_a_floor_in_another_unit_judges_nothing_and_the_number_is_reported(seams):
    """Hard rule 3 at the threshold. *Ignore below 200* is not a threshold;
    *200 gal/day* is — and comparing gal against a CCF meter suppresses every
    real leak or none, both of which look like a working check."""
    seams["batch"] = _batch([_day("WM-CCF", unit="ccf", intervals=24, nonzero=24)])
    seams["premises"] = [_address("WM-CCF")]
    result = _run(seams, {"ignore_below_unit": "gal"})
    checked = _checked(result, leak.STEP_FLAG)
    assert checked["floor_unit_mismatch"] == 1
    assert checked["continuous_flow"] == 0
    assert checked["meters_that_could_not_be_judged"] == 1


def test_a_meter_below_the_floor_is_reported_and_not_alerted(seams):
    """The floor is the level a utility bothers a customer at."""
    seams["batch"] = _batch([_day("WM-TINY", intervals=24, nonzero=24, quantity="40")])
    seams["premises"] = [_address("WM-TINY")]
    result = _run(seams)
    assert _checked(result, leak.STEP_FLAG)["below_the_floor"] == 1
    assert _tiles(result)["alerts"]["value"]["text"] == "0"


def test_a_meter_day_in_two_units_is_never_totalled(seams):
    """Adding gallons to litres produces a number with no meaning at all."""
    seams["batch"] = _batch([_day("WM-MIX", unit_conflict=True, quantity=None)])
    seams["premises"] = [_address("WM-MIX")]
    result = _run(seams)
    assert _checked(result, leak.STEP_FLAG)["meters_that_could_not_be_judged"] == 1


def test_a_quantity_without_a_unit_cannot_even_be_constructed():
    """Hard rule 3, enforced at the object rather than at the screen."""
    with pytest.raises(ValueError) as caught:
        leak.Finding(
            asset_id="a",
            meter_no="WM-1",
            account_id=None,
            account_label=None,
            address="14 Cedar St",
            pattern=leak.PATTERN_CONTINUOUS,
            hours=26,
            multiple=None,
            quantity=leak._decimal("1140"),
            unit=None,
            channel="text",
            outcome=leak.OUTCOME_PLANNED,
            reason="x",
            decided_by_rule="y",
            fix_route="accounts",
            fix_label="Open account →",
        )
    assert "EXPLICIT unit and one is never assumed" in str(caught.value)


# ── step 4 · the guards, and the one that has no column ───────────────────


def test_a_meter_told_this_week_is_skipped_not_sent(seams):
    """`RB-111`'s *Never include: Told this week*, read off the notice outbox
    because nothing in the product holds *"told about a leak on"* a date."""
    day = _day("WM-TOLD", intervals=48, nonzero=48)
    seams["batch"] = _batch([day])
    seams["premises"] = [_address("WM-TOLD")]
    seams["told"] = {day["asset_id"]: "2026-09-03"}
    result = _run(seams)
    assert _checked(result, leak.STEP_GUARDS)["told_this_week"] == 1
    assert _rows(result)["WM-TOLD"]["cells"]["sent"]["text"] == "Told this week"


def test_the_outbox_row_count_travels_beside_the_told_count(seams):
    """Hard-won law 7. *0 told over 0 rows* means NOBODY HAS BEEN TOLD YET;
    *0 told over 4,000 rows* means the guard ran and found nothing. One zero
    cannot say which, and this deployment only ever produces the first."""
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    result = _run(seams)
    assert _checked(result, leak.STEP_GUARDS)["outbox_rows_seen"] == 0
    assert _tiles(result)["told"]["detail"] == "0 in the notice outbox"


def test_an_account_in_dispute_is_never_alerted(seams):
    """A customer arguing about their usage does not need a text about it."""
    day = _day("WM-DISPUTE", intervals=48, nonzero=48)
    seams["batch"] = _batch([day])
    seams["premises"] = [_address("WM-DISPUTE")]
    seams["disputed"] = {day["unit_id"]}
    assert _checked(_run(seams), leak.STEP_GUARDS)["in_dispute"] == 1


def test_a_customer_with_no_channel_is_a_finding_and_not_a_silent_skip(seams):
    """`RB-111`'s own result names *1 no channel*, and its design note says the
    row with no channel is the data-hygiene runbook's problem — which it can
    only be if this runbook SAYS so."""
    day = _day("WM-03390", intervals=48, nonzero=48)
    seams["batch"] = _batch([day])
    seams["premises"] = [_address("WM-03390", "33 Bell Ave")]
    seams["channels"] = {f"acct-{day['unit_id']}": {"email": False, "text": False, "post": True}}
    result = _run(seams)
    row = _rows(result)["WM-03390"]
    assert row["cells"]["channel"]["text"] == "—"
    assert row["cells"]["sent"]["text"] == "No channel"
    assert _tiles(result)["no_channel"]["value"]["text"] == "1"


def test_a_sample_meter_is_guarded_and_still_counted(seams):
    """`BR-RBS-012` + `BR-RBS-035`: guarded is not the same as absent."""
    seams["batch"] = _batch(
        [_day("WM-REAL", intervals=48, nonzero=48), _day("WM-SAMPLE", sample=True)]
    )
    seams["premises"] = [_address("WM-REAL"), _address("WM-SAMPLE")]
    result = _run(seams)
    assert len(result.subjects) == 2
    assert [one.label for one in result.guarded] == ["WM-SAMPLE"]
    assert _checked(result, leak.STEP_GATHER)["sample_meters_guarded"] == 1


def test_the_cap_refuses_the_whole_run_and_never_truncates_it(seams):
    """`BR-RBS-006`. Queueing five of nine and dropping four is a failure that
    LOOKS like success."""
    days = [_day(f"WM-{n}", intervals=48, nonzero=48) for n in range(4)]
    seams["batch"] = _batch(days)
    seams["premises"] = [_address(f"WM-{n}") for n in range(4)]
    seams["cap"] = 2
    result = _run(seams)
    stop = result.set_results[leak.STEP_GUARDS]["stop"]
    assert stop["headline"] == "Too many alerts for one run."
    assert "would send 4 alerts and the limit is 2" in stop["detail"]
    assert "Nothing has been queued." in stop["detail"]
    assert "kpis" not in _blocks(result)


# ── hard rule 8 · the address is walked to, never read off the meter ──────


def test_the_address_comes_from_the_premises_and_is_drawn_on_the_row(seams):
    """`BR-MET-1161`: a meter, a service point, a unit and an account all
    declare no address column, so the alert's *"14 Cedar St"* is a walk."""
    seams["batch"] = _batch([_day("WM-04471", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-04471")]
    row = _rows(_run(seams))["WM-04471"]
    assert "14 Cedar St" in row["cells"]["account"]["text"]


def test_a_property_with_no_address_is_not_alerted_and_says_why(seams):
    """A leak alert that cannot say WHERE is a text nobody can act on."""
    seams["batch"] = _batch([_day("WM-NOADDR", intervals=48, nonzero=48)])
    seams["premises"] = []
    result = _run(seams)
    assert _checked(result, leak.STEP_NORMAL)["meters_with_no_address"] == 1
    assert result.records[0].outcome == leak.OUTCOME_NO_CHANNEL
    assert "cannot say where" in result.records[0].reason


def test_an_empty_property_is_nobody_to_tell_rather_than_a_dropped_row(seams):
    """A meter between tenancies is an ordinary state, and a runbook that told
    nobody must say so."""
    day = _day("WM-EMPTY", intervals=48, nonzero=48)
    seams["batch"] = _batch([day])
    seams["premises"] = [_address("WM-EMPTY")]
    seams["_no_account"] = {day["unit_id"]}
    result = _run(seams)
    assert _checked(result, leak.STEP_GUARDS)["nobody_to_tell"] == 1
    assert _rows(result)["WM-EMPTY"]["cells"]["sent"]["text"] == "Nobody to tell"


# ── BR-RBS-003 · the ports, and the one with no column ────────────────────


def test_queue_notice_is_called_and_its_own_refusal_is_the_outcome(seams):
    """`BR-RBS-003`: dry and live are ONE code path — no `is_bound` branch."""
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    result = _run(seams)
    assert result.records[0].outcome == leak.OUTCOME_PLANNED
    assert "no writer bound" in result.records[0].decided_by_rule


def test_the_kpi_says_to_queue_while_nothing_is_queued(seams):
    """A tile reading *9 Alerts queued* over a run that queued nothing is the
    most dangerous sentence this screen could print."""
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    tiles = _tiles(_run(seams))
    assert tiles["alerts"]["label"] == "To queue"
    assert tiles["alerts"]["detail"] == "Planned — nothing is queued yet"


def test_step_six_records_nothing_and_says_why_in_words(seams):
    """`flag_meter` binds no writer: there is no column anywhere to hold *"told
    about a leak on"* a date, and `Asset` lives in a module a port may not write.

    ⚠ And `BR-RBS-040` forbids the obvious substitute — a note is an ENGINE act,
    never a fourteenth port — so the step counts and reports.
    """
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    checked = _checked(_run(seams), leak.STEP_RECORD)
    assert checked["would_record"] == 1
    assert checked["recorded"] == 0
    assert "no writer bound" in checked["why_not"]


def test_it_declares_exactly_the_two_ports_the_card_names(seams):
    assert leak.RUNBOOK.ports == ("queue_notice", "flag_meter")


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_is_one_of_the_twelve(seams):
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    assert set(_blocks(_run(seams))) <= set(BLOCK_TYPES)


def test_the_usage_cell_carries_its_unit_and_the_header_does_not(seams):
    """`RB-111`'s header reads *Gal / day*, which hard-codes one utility's unit.

    A tenant metering in CCF would read that header over numbers that are not
    gallons. The unit travels in the CELL, where it cannot be right for some
    rows and wrong for others.
    """
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48, quantity="1140")])
    seams["premises"] = [_address("WM-1")]
    payload = _blocks(_run(seams))["records"]
    headers = [column["label"] for column in payload["columns"]]
    assert "Gal / day" not in headers
    assert "Usage" in headers
    assert payload["rows"][0]["cells"]["usage"]["text"].endswith(" gal")


def test_the_water_at_stake_tile_uses_the_floors_own_unit(seams):
    """A total across two units is not a quantity, and a tile that showed one
    anyway would be labelled with whichever unit happened to sort first.

    ⚠ **THIS ASSERTS THE INVARIANT THAT MAKES THE MIXED-UNIT ARM UNREACHABLE,
    WHICH IS THE ONLY HONEST WAY TO TEST IT.** Step 3 refuses to judge a meter
    whose unit is not the floor's, so every meter that reaches the tile already
    shares one unit and the *"more than one unit"* branch cannot currently fire.
    The branch is kept — the floor could reasonably become per-service one day —
    and this case is what goes red if the gate that makes it dead is removed:
    the CCF meter must be excluded from the total, not added to it.
    """
    seams["batch"] = _batch(
        [
            _day("WM-A", intervals=48, nonzero=48, unit="gal", quantity="1140"),
            _day("WM-B", intervals=48, nonzero=48, unit="ccf", quantity="4000"),
        ]
    )
    seams["premises"] = [_address("WM-A"), _address("WM-B")]
    result = _run(seams, {"ignore_below_unit": "gal"})
    tile = _tiles(result)["at_stake"]
    assert tile["value"]["text"] == "1140 gal"
    assert _checked(result, leak.STEP_FLAG)["floor_unit_mismatch"] == 1


def test_no_rule_id_and_no_database_id_reaches_a_clerk(seams):
    """B14 rules 31 and 32. The rule travels in `meta`, which no block draws."""
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    rows = _blocks(_run(seams))["records"]["rows"]
    drawn = repr([row["cells"] for row in rows])
    assert "BR-" not in drawn
    assert "asset-" not in drawn
    assert "acct-" not in drawn
    assert rows[0]["meta"]["decided_by_rule"]


def test_every_listed_row_names_a_fix_route(seams):
    """`BR-RBS-011`. A finding with nowhere to go is a defect in the runbook."""
    seams["batch"] = _batch([_day("WM-1", intervals=48, nonzero=48)])
    seams["premises"] = [_address("WM-1")]
    for row in _run(seams).records:
        assert row.fix_route


def test_the_empty_state_says_what_was_examined(seams):
    """*0 leaks* over 1,840 meters and over nothing are different mornings."""
    seams["batch"] = _batch([_day("WM-TINY", intervals=24, nonzero=24, quantity="40")])
    seams["premises"] = [_address("WM-TINY")]
    empty = _blocks(_run(seams))["records"]["empty"]
    assert "1 meters read over 48 hours" in empty["helper"]
    assert "1 used less than the floor" in empty["helper"]


def test_the_records_empty_payload_matches_what_the_renderer_reads(seams):
    """`DEF-RBS-4352` one level down: `RecordsBlock.tsx` reads `title` and
    `helper`, and `PAYLOAD_FIELDS` only checks the top-level key `empty`."""
    seams["batch"] = _batch([_day("WM-TINY", intervals=24, nonzero=24, quantity="40")])
    seams["premises"] = [_address("WM-TINY")]
    assert set(_blocks(_run(seams))["records"]["empty"]) == {"title", "helper"}


def test_a_refusal_sentence_stays_within_six_words(seams):
    """B14 rule 33."""
    for label in leak.PATTERN_LABELS.values():
        assert len(label.split()) <= 6, label
