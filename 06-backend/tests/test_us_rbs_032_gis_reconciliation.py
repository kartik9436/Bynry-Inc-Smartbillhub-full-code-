# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-032 (EP-RBS-05) — CR-075 wave Q′, runbook 20.
# Rules:    BR-RBS-002 · BR-RBS-004 · BR-RBS-006 · BR-RBS-011 · BR-RBS-012 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-027 · BR-RBS-035 ·
#           RBR-17 · CLAUDE.md hard rule 8 · B14 rules 31 and 32
# Tests:    this file. The PostgreSQL half — the real seams and the savepoint —
#           is tests/test_rbs_sync_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/gis_reconciliation.py
# ───────────────────────────────────────────────────────
"""Runbook 20, against the rules rather than against itself.

**EVERY CASE HERE ASSERTS A RULE AND NOT AN IMPLEMENTATION.** A test asserting
*"step 4 returns a dict with five keys"* would go green over a runbook that had
stopped honouring the never-touch list, which is the one thing in this runbook
that cannot move.

⚠ **THE SEAMS ARE REPLACED, AND WHAT THAT DOES AND DOES NOT PROVE IS STATED.**
These cases hand the runbook fixed answers so the DECISIONS can be exercised — a
never-touch conflict, two premises on one parcel, a cap that refuses, a sample
row — none of which a seeded tenant happens to contain in one batch. **It proves
the runbook's reasoning and it proves NOTHING about the seams**: a seam returning
the wrong shape passes every case in this file. That is what
`tests/test_rbs_sync_runbooks_pg.py` is for, and it runs the REAL seams against
real rows on real PostgreSQL. Both numbers are quoted in the lane report; neither
is quoted alone.
"""

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import gis_reconciliation as gis
from apps.runbooks.engine import executor

#: ⚠ **THE WHOLE FILE NEEDS A DATABASE, AND NOT BECAUSE THESE CASES READ ONE.**
#: The executor opens a nested `transaction.atomic()` around every per-record
#: step — the SAVEPOINT hard-won law 14 makes non-negotiable — and
#: `transaction.atomic()` asks for a connection before it does anything else.
#: Marked at module level rather than case by case, because the day somebody
#: removes it the failure is a `RuntimeError` about database access and reads
#: nothing like *the savepoint went away*.
pytestmark = pytest.mark.django_db

BATCH_ID = "batch-20"


def _premises(
    premises_id="p1",
    label="P-00074",
    address="1408 Bluestem Ln",
    city="Katy",
    state="TX",
    postal="77494",
    owner="Whitfield Rentals LLC",
    ptype="single_family",
    ptype_label="Single-family",
    inside=None,
    sample=False,
    external_ref=None,
):
    return {
        "premises_id": premises_id,
        "label": label,
        "premise_no": label,
        "external_ref": external_ref,
        "address_line": address,
        "city": city,
        "state": state,
        "postal_code": postal,
        "owner_manager": owner,
        "premises_type": ptype,
        "premises_type_label": ptype_label,
        "inside_city_limits": inside,
        "lat": None,
        "lng": None,
        "gis_unchecked": False,
        "is_sample": sample,
    }


def _parcel(row_no=1, ref="88214", sample=False, **mapped):
    """One row of the county's file, AS MAPPED.

    ⚠ **AN UNKNOWN KEY IS REFUSED, AND THAT IS NOT TIDINESS.** The first draft
    of this helper accepted anything: three cases passed `address=` where the
    mapped column is `address_line`, so the override went into a key the runbook
    never reads and the parcel silently matched the DEFAULT address. Two of them
    then failed for a reason that looked like a bug in the runbook, and one —
    the standardised-address case — **passed for the wrong reason entirely**,
    which is the shape hard-won law 7 calls a check you cannot describe a false
    pass for.
    """
    base = {
        "address_line": "1408 Bluestem Ln",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "owner_manager": "Whitfield Rentals LLC",
        "premises_type": "single_family",
        "premises_type_raw": "Single-family",
        "external_ref": ref,
    }
    unknown = set(mapped) - set(base)
    assert not unknown, f"the mapped row has no column(s) {sorted(unknown)}"
    base.update(mapped)
    return {
        "row_no": row_no,
        "source_key": ref,
        "raw": {},
        "mapped": base,
        "outcome": "flagged",
        "is_sample": sample,
    }


def _batch(rows, *, sample=False):
    return {
        "run_id": BATCH_ID,
        "target": "premises",
        "status": "validated",
        "file_name": "county-parcels.csv",
        "batch_label": "County parcels",
        "is_sample": sample,
        "rows": rows,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the three reads runbook 20 makes.

    Everything defaults to *nothing is connected and nothing was uploaded*,
    which is the STOP — so a case that forgets to give the runbook work cannot
    accidentally assert on a happy path.
    """
    state = {
        "connections": [],
        "batch": None,
        "premises": [],
        "cap": None,
        # ⚠ `DEF-INT-9848` (2026-10-07) — a working connection now ASKS the
        # City through `integrations_seam.city_parcels`. Fixed here to a City
        # that answered and sent nothing, so no case below dials anything; the
        # City door's own cases live in `test_def_int_9848_runbook_20_city_door.py`.
        "city": {
            "stopped": False, "complete": True, "headline": "", "differences": [],
            "queue": [], "counts": {"city_rows": 0, "city_pages": 1, "city_pages_total": 1},
        },
        "asked": [],
    }
    monkeypatch.setattr(
        gis.integrations_seam, "live_connections", lambda keys: list(state["connections"])
    )

    def city_parcels(**kwargs):
        state["asked"].append(kwargs)
        return dict(state["city"])

    monkeypatch.setattr(gis.integrations_seam, "city_parcels", city_parcels)
    monkeypatch.setattr(
        gis.metering_seam,
        "staged_import_batch",
        lambda target, run_id=None: state["batch"],
    )
    monkeypatch.setattr(
        gis.metering_seam,
        "premises_for_reconciliation",
        lambda include_sample=False: list(state["premises"]),
    )
    monkeypatch.setattr(gis, "_cap", lambda ctx: state["cap"])
    return state


def _run(params=None):
    definition = gis.RUNBOOK
    ctx = executor.build_context(definition, tenant_id="t", run_id=None, params=params or {})
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


# ── step 1 · the two doors ────────────────────────────────────────────────


def test_both_doors_shut_stops_the_run_and_names_both_absences(seams):
    """PO 2026-09-06: *"in absence of API conenctions … that is a valid case"*."""
    result = _run()
    stop = (result.set_results[gis.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing to compare."
    assert "No GIS connection is set up." in stop["detail"]
    assert "Nobody has uploaded a parcel file either" in stop["detail"]
    assert stop["fix_label"] == "Upload parcels"


def test_a_stopped_run_draws_no_kpi_strip(seams):
    """A strip of zeros over a run that examined nothing reads like a clean day.

    Hard-won law 7: *a run that examined nothing and a run that found nothing
    wrong must not read the same.* The strip is ABSENT, not zeroed.
    """
    blocks = _blocks(_run())
    assert "kpis" not in blocks
    assert set(blocks) == {"verdict", "sentence", "chain", "records"}


def test_a_stopped_run_says_stopped_and_never_says_failed(seams):
    """`BR-RBS-027` and the PO's ruling: this is a STATE, not a failure."""
    result = _run()
    blocks = _blocks(result)
    assert blocks["verdict"]["word"] == "Stopped"
    everything = str(result.report).lower()
    assert "failed" not in everything
    assert "error" not in everything


def test_every_later_step_reads_never_reached(seams):
    """`BR-RBS-027` — a blank cell reads as *nothing wrong*; this says otherwise."""
    cells = _blocks(_run())["chain"]["cells"]
    assert len(cells) == len(gis.STEP_LABELS)
    assert cells[0]["state"] == "bad"
    assert [one["note"] for one in cells[1:]] == ["Never reached"] * (len(cells) - 1)


def test_a_working_connection_and_nothing_landed_is_a_different_sentence(seams):
    """⚠ **THE HOLD THAT EXPIRED ON 2026-10-07 (`DEF-INT-9848`).** Until then
    this case asserted the stub's sentence for EVERY working connection,
    because the City was never asked. The sentence now means what it says —
    the City WAS asked, once, and sent no parcels."""
    seams["connections"] = [
        {"key": "gis_esri", "display_name": "Esri ArcGIS", "enabled": True, "status": "working"}
    ]
    stop = (_run().set_results[gis.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing has landed yet."
    assert "Esri ArcGIS is connected" in stop["detail"]  # City GIS until CR-110-BRC04
    assert "the city sent no parcels" in stop["detail"]
    assert len(seams["asked"]) == 1


def test_an_uploaded_file_wins_over_the_city_and_the_city_is_not_asked(seams):
    """A person who uploaded the county's file meant that file."""
    seams["connections"] = [
        {"key": "gis_esri", "display_name": "Esri ArcGIS", "enabled": True, "status": "working"}
    ]
    seams["batch"] = _batch([_parcel()])
    result = _run()
    assert "stop" not in result.set_results[gis.STEP_GATHER]
    assert result.set_results[gis.STEP_GATHER]["checked"]["source"] == "file"
    assert seams["asked"] == []


def test_a_connection_that_is_switched_off_is_named_as_such(seams):
    seams["connections"] = [
        {"key": "gis_esri", "display_name": "Esri ArcGIS", "enabled": False, "status": "working"}
    ]
    stop = (_run().set_results[gis.STEP_GATHER])["stop"]
    assert "A GIS connection is set up and switched off." in stop["detail"]


def test_a_batch_that_was_asked_for_and_is_not_there_is_its_own_stop(seams):
    """Telling a clerk *nobody uploaded a file* when they chose one is a lie."""
    stop = (_run({"batch": "gone"}).set_results[gis.STEP_GATHER])["stop"]
    assert stop["headline"] == "That parcel file is not here."
    assert "already have been loaded, or rolled back" in stop["detail"]


# ── step 2 · the match ladder ─────────────────────────────────────────────


def test_the_parcel_id_beats_the_standardised_address(seams):
    seams["premises"] = [
        _premises("p1", "P-1", address="Somewhere Else", external_ref="88214"),
        _premises("p2", "P-2", address="1408 Bluestem Ln"),
    ]
    seams["batch"] = _batch([_parcel(ref="88214")])
    checked = _checked(_run(), gis.STEP_MATCH)
    assert checked["matched_on_parcel_id"] == 1
    assert checked["matched_on_standardised_address"] == 0


def test_the_address_key_ignores_case_and_punctuation(seams):
    seams["premises"] = [_premises(address="1408 Bluestem Ln.")]
    seams["batch"] = _batch([_parcel(ref="", address_line="1408  BLUESTEM LN")])
    assert _checked(_run(), gis.STEP_MATCH)["matched_on_standardised_address"] == 1


def test_two_premises_on_one_parcel_are_queued_never_taken_by_the_first(seams):
    seams["premises"] = [
        _premises("p1", "P-1", address="1408 Bluestem Ln"),
        _premises("p2", "P-2", address="1408 Bluestem Ln"),
    ]
    seams["batch"] = _batch([_parcel()])
    plan = (_run().set_results[gis.STEP_CAP])["plan"]
    assert [one["difference_class"] for one in plan] == [gis.CLASS_TWO_PREMISES_ONE_PARCEL]
    assert plan[0]["disposition"] == gis.DISPOSITION_QUEUE
    assert plan[0]["fix_label"] == "Open both →"


def test_one_premises_named_by_two_parcels_is_queued(seams):
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel(1, ref="88214"), _parcel(2, ref="88215")])
    plan = (_run().set_results[gis.STEP_CAP])["plan"]
    assert {one["difference_class"] for one in plan} == {gis.CLASS_ONE_PREMISE_TWO_PARCELS}


def test_a_parcel_with_no_premises_is_listed_and_never_created(seams):
    """`OQ-INT-1472`, CLOSED 2026-09-04: the night creates nothing."""
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel(2, ref="88999", address_line="77 Nowhere Rd")])
    plan = (_run().set_results[gis.STEP_CAP])["plan"]
    row = next(one for one in plan if one["difference_class"] == gis.CLASS_UNMATCHED)
    assert row["disposition"] == gis.DISPOSITION_NEVER
    assert "nothing is created from it" in row["reason"]


def test_create_premises_switched_on_queues_the_unmatched_instead(seams):
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel(2, ref="88999", address_line="77 Nowhere Rd")])
    plan = (_run({"create_premises_we_do_not_have": True}).set_results[gis.STEP_CAP])["plan"]
    row = next(one for one in plan if one["difference_class"] == gis.CLASS_UNMATCHED)
    assert row["disposition"] == gis.DISPOSITION_QUEUE


# ── step 3 · the classes ──────────────────────────────────────────────────


def test_a_column_the_file_does_not_carry_is_not_a_difference(seams):
    """Otherwise every premises reports *blank there* on every unmapped field."""
    seams["premises"] = [_premises()]
    seams["batch"] = _batch(
        [{"row_no": 1, "source_key": "88214", "raw": {}, "mapped": {"address_line": "1408 Bluestem Ln"}, "outcome": "flagged", "is_sample": False}]
    )
    checked = _checked(_run(), gis.STEP_CLASSIFY)
    assert checked["differences_found"] == 0
    assert "City" in checked["fields_the_file_does_not_carry"]


def test_the_premises_type_is_compared_on_the_code_and_shown_by_its_name(seams):
    seams["premises"] = [_premises(ptype="apartment_complex", ptype_label="Apartment complex")]
    seams["batch"] = _batch([_parcel(premises_type="mixed_use", premises_type_raw="Mixed-use")])
    plan = (_run().set_results[gis.STEP_CAP])["plan"]
    row = next(one for one in plan if one["field"] == "premises_type")
    assert row["ours"] == "Apartment complex"
    assert row["theirs"] == "Mixed-use"


def test_a_matching_type_reports_no_difference_even_though_the_words_differ(seams):
    """The importer resolves *Single-family* onto `single_family`; the codes agree."""
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel()])
    assert _checked(_run(), gis.STEP_CLASSIFY)["differences_found"] == 0


def test_a_blank_on_their_side_is_its_own_class(seams):
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel(owner_manager="")])
    plan = (_run().set_results[gis.STEP_CAP])["plan"]
    assert plan[0]["difference_class"] == gis.CLASS_BLANK_THERE


def test_a_blank_on_our_side_is_the_other_class(seams):
    seams["premises"] = [_premises(owner=None)]
    seams["batch"] = _batch([_parcel()])
    plan = (_run().set_results[gis.STEP_CAP])["plan"]
    assert plan[0]["difference_class"] == gis.CLASS_BLANK_HERE


# ── step 4 and 5 · the never-touch list, and the cap ──────────────────────


def test_a_never_touch_field_is_never_applied_however_the_tenant_sets_it(seams):
    """`RBR-17` — fixed on the money-path fields and NOT widenable by a tenant.

    ⚠ This is the case that must never go green by accident. A tenant putting
    `city` in *Apply automatically* is exactly the back door the rule closes.
    """
    seams["premises"] = [_premises(city="Katy")]
    seams["batch"] = _batch([_parcel(city="Fulshear")])
    result = _run({"apply_automatically": ("city", "postal_code")})
    plan = (result.set_results[gis.STEP_CAP])["plan"]
    row = next(one for one in plan if one["field"] == "city")
    assert row["disposition"] == gis.DISPOSITION_NEVER
    assert row["outcome"] == gis.OUTCOME_NEVER_TOUCHED
    assert _checked(result, gis.STEP_CAP)["automatic_changes_planned"] == 0


def test_a_never_touch_conflict_is_listed_rather_than_hidden(seams):
    """`RB-120`'s design note: a county disagreeing about a boundary is worth knowing."""
    seams["premises"] = [_premises(state="TX")]
    seams["batch"] = _batch([_parcel(state="LA")])
    blocks = _blocks(_run())
    assert blocks["kpis"]["tiles"][2]["label"] == "Never touched"
    assert blocks["kpis"]["tiles"][2]["value"]["text"] == "1"


def test_the_cap_refuses_the_run_and_never_truncates(seams):
    """`BR-RBS-006` · `TC-RBS-3` — a cap REFUSES; it does not apply the first N."""
    seams["premises"] = [
        _premises(f"p{i}", f"P-{i}", address=f"{i} Somewhere Rd", postal="77494")
        for i in range(4)
    ]
    seams["batch"] = _batch(
        [_parcel(i, ref=f"9000{i}", address_line=f"{i} Somewhere Rd", postal_code="77000") for i in range(4)]
    )
    seams["cap"] = 2
    result = _run()
    stop = (result.set_results[gis.STEP_CAP])["stop"]
    assert stop["headline"] == "More changes than this runbook may make."
    assert "4 changes would be applied and the limit is 2" in stop["detail"]
    assert "Nothing has been changed." in stop["detail"]
    assert gis.OUTCOME_APPLIED not in result.counts


def test_a_cap_of_none_is_not_a_limit_of_zero(seams):
    seams["premises"] = [_premises(postal="77494")]
    seams["batch"] = _batch([_parcel(postal_code="77000")])
    seams["cap"] = None
    result = _run()
    assert (result.set_results[gis.STEP_CAP]).get("stop") is None
    assert _checked(result, gis.STEP_CAP)["automatic_changes_planned"] == 1


# ── the guard ─────────────────────────────────────────────────────────────


def test_a_sample_parcel_is_guarded_counted_and_seen_by_no_step(seams):
    """`BR-RBS-012` · `BR-RBS-035` — absolute, and it still appears in the totals."""
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel(1, ref="88214"), _parcel(2, ref="88215", sample=True)])
    result = _run()
    assert len(result.subjects) == 2
    assert [one.subject_id for one in result.guarded] == ["88215"]
    assert result.counts[executor.OUTCOME_SKIPPED] == 1
    assert _checked(result, gis.STEP_MATCH)["parcels_examined"] == 1


def test_a_sample_batch_guards_every_row_in_it(seams):
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel()], sample=True)
    result = _run()
    assert len(result.guarded) == 1
    assert _checked(result, gis.STEP_MATCH)["parcels_examined"] == 0


# ── step 6 · the port ─────────────────────────────────────────────────────


def test_the_port_is_called_and_its_own_refusal_is_the_outcome(seams):
    """`BR-RBS-003` — dry and live are ONE path; there is no `if is_bound` branch."""
    seams["premises"] = [_premises(postal="77494")]
    seams["batch"] = _batch([_parcel(postal_code="77000")])
    result = _run()
    record = result.records[0]
    assert record.outcome == gis.OUTCOME_PLANNED
    assert "has no writer bound" in record.decided_by_rule
    assert "Nothing is changed yet." in record.reason


def test_a_parcel_that_agrees_says_so_rather_than_vanishing(seams):
    seams["premises"] = [_premises()]
    seams["batch"] = _batch([_parcel()])
    assert _run().records[0].outcome == gis.OUTCOME_AGREES


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    """`BR-RBS-021` — a thirteenth is refused at close, in both compositions."""
    seams["premises"] = [_premises(postal="77494")]
    seams["batch"] = _batch([_parcel(postal_code="77000")])
    for report in (_run().report, _run({"batch": "gone"}).report):
        assert {block["block"] for block in report} <= set(BLOCK_TYPES)


def test_ours_and_theirs_are_on_every_queued_row(seams):
    """`US-RBS-032`'s acceptance sentence, asserted as a sentence and not a shape."""
    seams["premises"] = [_premises(owner="Mason Rd Holdings")]
    seams["batch"] = _batch([_parcel(owner_manager="Mason Road Holdings LLC")])
    payload = _blocks(_run())["row_decisions"]
    assert [one["label"] for one in payload["columns"]][2:4] == ["Ours", "Theirs"]
    assert [one["id"] for one in payload["choices"]] == ["accept_theirs", "keep_ours"]
    for row in payload["rows"]:
        assert row["cells"]["ours"]["text"]
        assert row["cells"]["theirs"]["text"]


def test_an_ambiguous_match_is_not_offered_accept_theirs(seams):
    """There are no two named values to choose between; the card says *Open both*."""
    seams["premises"] = [
        _premises("p1", "P-1", address="1408 Bluestem Ln"),
        _premises("p2", "P-2", address="1408 Bluestem Ln"),
    ]
    seams["batch"] = _batch([_parcel()])
    blocks = _blocks(_run())
    assert blocks["row_decisions"]["rows"] == []
    assert blocks["records"]["total"] == 1


def test_no_rule_id_reaches_a_drawn_cell(seams):
    """B14 rule 32 — the rule travels in `meta`, which no block draws."""
    seams["premises"] = [_premises(owner="Mason Rd Holdings")]
    seams["batch"] = _batch([_parcel(owner_manager="Mason Road Holdings LLC")])
    for block in _run().report:
        for row in block["payload"].get("rows", []):
            drawn = " ".join(
                str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
            )
            assert "BR-RBS" not in drawn
            assert "RBR-" not in drawn


def test_no_database_id_is_the_visible_value_of_a_field(seams):
    """B14 rule 31 — PO 2026-08-30: *"no Databse ID on screen - that is a rule"*."""
    seams["premises"] = [_premises("01a0-uuid-here", "P-00074", owner="Mason Rd Holdings")]
    seams["batch"] = _batch([_parcel(owner_manager="Mason Road Holdings LLC")])
    for block in _run().report:
        for row in block["payload"].get("rows", []):
            for cell in row["cells"].values():
                assert "01a0-uuid-here" not in str(cell)


def test_the_by_class_table_and_the_tiles_agree(seams):
    """The card's own tiles overlap if read naively; these must add up."""
    seams["premises"] = [
        _premises("p1", "P-1", address="a rd", postal="77494", city="Katy"),
        _premises("p2", "P-2", address="b rd", owner="Ours"),
    ]
    seams["batch"] = _batch(
        [
            _parcel(1, ref="1", address_line="a rd", postal_code="77000", city="Fulshear"),
            _parcel(2, ref="2", address_line="b rd", owner_manager="Theirs"),
            _parcel(3, ref="3", address_line="nowhere at all"),
        ]
    )
    blocks = _blocks(_run())
    tiles = {one["id"]: int(one["value"]["text"]) for one in blocks["kpis"]["tiles"]}
    by_class = sum(
        int(row["cells"]["count"]["text"]) for row in blocks["breakdown"]["rows"]
    )
    assert tiles["applied"] + tiles["queued"] + tiles["never"] + tiles["unmatched"] == by_class


def test_a_stopped_run_carries_a_what_to_do_box(seams):
    sentence = _blocks(_run())["sentence"]
    assert sentence["label"] == "What to do"
    assert "Upload the county's parcel file" in sentence["text"]
