"""CR-112 — the run: preview writes nothing, apply writes only what was turned on.

⚠ **THE WRITER IS INJECTED AND RECORDS WHAT IT WAS ASKED TO DO**, so *what the
run decided to write* is testable without a database. Whether metering's own
service accepts those patches is metering's test, and whether a refused row
poisons the transaction is `test_cr112_gis_parcels_pg.py`'s — that one needs
real PostgreSQL, because the default suite is in-memory SQLite and **has no
aborted-transaction state at all** (hard-won law 14).
"""

from __future__ import annotations

import pytest

from apps.integrations import gis_esri_fixtures as fx
from apps.integrations import gis_parcels
from apps.integrations.gis_parcels import APPLY, BY_PERSON, BY_SCHEDULE, PREVIEW, GisRunRefused

# ⚠ **THE APPLY PATH OPENS A REAL SAVEPOINT, SO IT NEEDS A REAL DATABASE — AND
# FAKING THAT AWAY WOULD REMOVE THE ONE THING WORTH TESTING** (hard-won law 14).
# `_persist` wraps each row in a nested `transaction.atomic()`; a test that
# patched it out would pass over an implementation that had dropped the
# savepoint, which is exactly the defect that law exists for. The suite runs on
# in-memory SQLite, which has no aborted-transaction state, so this proves the
# savepoint is TAKEN and `test_cr112_gis_parcels_pg.py` proves it WORKS.
pytestmark = pytest.mark.django_db

CONNECTION = {"layer_url": fx.FIXTURE_LAYER}


def our_register():
    return {
        "premises": [
            {"id": "P1", "premise_no": "P-00001", "label": "P-00001",
             "address_line": "100 North Maple Street", "city": "Oldname",
             "state": "MI", "postal_code": "48104", "lat": None, "lng": None,
             "gis_parcel_id": None, "gis_parcel_id_was": None, "gis_status": None},
            {"id": "P2", "premise_no": "P-00002", "label": "P-00002",
             "address_line": "220 Oak Ave", "city": "Riverbend",
             "state": "MI", "postal_code": "48104", "lat": None, "lng": None,
             "gis_parcel_id": None, "gis_parcel_id_was": None, "gis_status": None},
        ],
        "units_by_premises": {
            "P2": [
                {"id": "U1", "label": "1", "gis_point_id": None,
                 "gis_point_id_was": None, "lat": None, "lng": None, "gis_status": None},
                {"id": "U2", "label": "2", "gis_point_id": None,
                 "gis_point_id_was": None, "lat": None, "lng": None, "gis_status": None},
            ]
        },
    }


class Recorder:
    """A writer that records instead of writing."""

    def __init__(self):
        self.calls = []

    def __call__(self, actor, row_id, patch):
        self.calls.append((row_id, dict(patch)))

    def patch_for(self, row_id):
        return next((p for r, p in self.calls if r == row_id), None)


def go(**kw):
    premises_writer = kw.pop("premises_writer", Recorder())
    unit_writer = kw.pop("unit_writer", Recorder())
    result = gis_parcels.run(
        "actor",
        connection_config=kw.pop("connection_config", CONNECTION),
        ours=kw.pop("ours", our_register()),
        transport=kw.pop("transport", fx.recorded_transport),
        update_premises=premises_writer,
        update_unit=unit_writer,
        **kw,
    )
    return result, premises_writer, unit_writer


# ── F · the trigger ─────────────────────────────────────────────────────────


def test_preview_is_the_default_mode():
    """Hard-won law 3 — the unsafe option is the one somebody types."""
    result, _, _ = go()
    assert result["mode"] == PREVIEW


def test_a_preview_writes_absolutely_nothing():
    """⚠ Not the keys, not the fields, NOT THE VERIFIED STAMP."""
    result, premises_writer, unit_writer = go(mode=PREVIEW, settings={
        "gis_field_dispositions": {"city": "apply", "lat": "apply"}
    })
    assert premises_writer.calls == []
    assert unit_writer.calls == []
    assert result["applied"] == {}
    assert result["counts"]["differences_found"] > 0, "it still did all the work"


def test_a_preview_and_an_apply_find_the_same_differences():
    """They are one code path up to the write; this is what says so."""
    preview, _, _ = go(mode=PREVIEW)
    applied, _, _ = go(mode=APPLY)
    assert preview["counts"]["differences_found"] == applied["counts"]["differences_found"]
    assert preview["headline"] == applied["headline"]


def test_a_person_starting_a_run_must_be_named():
    with pytest.raises(GisRunRefused, match="no name was recorded"):
        go(started_by=BY_PERSON)


def test_a_named_person_travels_with_the_run():
    result, _, _ = go(started_by=BY_PERSON, started_by_name="D. Whitfield")
    assert result["started_by"] == BY_PERSON
    assert result["started_by_name"] == "D. Whitfield"


def test_the_schedule_needs_no_name():
    result, _, _ = go(started_by=BY_SCHEDULE)
    assert result["started_by"] == BY_SCHEDULE


def test_an_unknown_mode_is_refused_by_name():
    with pytest.raises(GisRunRefused, match="not a mode"):
        go(mode="sort-of-apply")


def test_an_apply_with_no_writer_bound_refuses_rather_than_doing_nothing():
    """Law 2 — an `apply` that quietly applied nothing would pass every test."""
    with pytest.raises(GisRunRefused, match="no premises writer is bound"):
        gis_parcels.run(
            "actor", connection_config=CONNECTION, ours=our_register(),
            transport=fx.recorded_transport, mode=APPLY,
        )


# ── ruling 9 · the first runs change no addresses, visibly ──────────────────


def test_an_apply_on_a_fresh_tenant_stores_keys_and_changes_no_address():
    result, premises_writer, _ = go(mode=APPLY)
    patch = premises_writer.patch_for("P1")
    assert patch["gis_parcel_id"] == "09-01-100"
    assert patch["gis_verified"] is True
    # The City says Riverbend and we say Oldname. Nobody turned `city` on.
    assert "city" not in patch
    assert result["applied"]["fields_applied"] == 0


def test_the_headline_says_why_nothing_was_applied():
    """Or a clerk reports the screen as broken."""
    result, _, _ = go(mode=APPLY)
    assert result["headline"].endswith("fields set to never touch")
    assert result["counts"]["fields_set_to_never_touch"] == 7


def test_a_field_turned_on_is_applied_and_counted():
    result, premises_writer, _ = go(
        mode=APPLY, settings={"gis_field_dispositions": {"city": "apply"}}
    )
    assert premises_writer.patch_for("P1")["city"] == "Riverbend"
    assert result["applied"]["fields_applied"] == 1


# ── the keys, and what a replaced key leaves behind ─────────────────────────


def test_a_first_key_records_no_history():
    """A new key is not a change; recording one makes every row look churned."""
    _, premises_writer, _ = go(mode=APPLY)
    patch = premises_writer.patch_for("P1")
    assert "gis_parcel_id_was" not in patch


def test_a_replaced_key_records_what_it_was_and_when():
    ours = our_register()
    ours["premises"][0]["gis_parcel_id"] = "OLD-RETIRED"
    _, premises_writer, _ = go(mode=APPLY, ours=ours)
    patch = premises_writer.patch_for("P1")
    assert patch["gis_parcel_id"] == "09-01-100"
    assert patch["gis_parcel_id_was"] == "OLD-RETIRED"
    assert patch["gis_key_changed_at"] is not None


def test_a_unit_gets_its_point_key_inside_its_building_parcel():
    _, _, unit_writer = go(mode=APPLY)
    assert unit_writer.patch_for("U1")["gis_point_id"] == "09-01-200-0001"
    assert unit_writer.patch_for("U2")["gis_point_id"] == "09-01-200-0002"


def test_a_row_that_matched_nothing_is_never_written():
    ours = our_register()
    ours["premises"][0]["address_line"] = "9 Nowhere Rd"
    _, premises_writer, _ = go(mode=APPLY, ours=ours)
    assert premises_writer.patch_for("P1") is None
    assert premises_writer.patch_for("P2") is not None


# ── BR-INT-072 · a broken pull stops the run and changes nothing ────────────


def test_a_half_pull_stops_the_run_and_writes_nothing():
    """A half snapshot reads as *the City deleted 40,000 addresses*."""
    result, premises_writer, _ = go(mode=APPLY, transport=fx.half_way_transport)
    assert result["stopped"] is True
    assert premises_writer.calls == []
    assert "could not be read in full" in result["headline"]


def test_a_projected_answer_stops_the_run():
    result, premises_writer, _ = go(mode=APPLY, transport=fx.projected_transport)
    assert result["stopped"] is True
    assert premises_writer.calls == []


def test_a_renamed_field_stops_the_run_rather_than_filing_a_difference_per_row():
    result, premises_writer, _ = go(
        mode=APPLY,
        connection_config={
            "layer_url": fx.FIXTURE_LAYER,
            "field_mapping": {"parcel_field": "PARCELNO"},
        },
    )
    assert result["stopped"] is True
    assert "does not carry the fields" in result["headline"]
    assert premises_writer.calls == []


# ── BR-INT-037 · nothing city-specific is in the code ───────────────────────


def test_the_parcel_and_point_fields_are_per_tenant_configuration():
    """Another city, differently-named layer, same connector."""
    config = gis_parcels.config_from_connection(
        {"layer_url": "https://other.example/FeatureServer/2",
         "field_mapping": {"parcel_field": "TAXLOT", "point_field": "ADDRPT", "unit": "APTNO"}}
    )
    assert config.parcel_field == "TAXLOT"
    assert config.point_field == "ADDRPT"
    assert config.fields["unit"] == "APTNO"
    assert config.fields["city"] == "City", "unmapped keys keep their default"


def test_no_city_identifier_appears_in_the_modules():
    """`BR-INT-037` — *"adding an API is data, not code"*.

    ⚠ **THIS BANS IDENTIFIERS, NOT THE CITY'S NAME IN PROSE, AND THE FIRST
    VERSION GOT THAT WRONG.** It banned the string `ann arbor` outright and
    failed on `gis_layer.py`'s own docstring — which says *"Not in: anything
    about Ann Arbor"*, i.e. the sentence that STATES the rule. A check that
    refuses the documentation of the thing it enforces is a check nobody keeps.

    What must never appear is anything a machine could USE: a host, a service
    path, a layer name. Those are configuration. The city's name in a sentence
    explaining why they are configuration is the opposite of the defect.
    """
    import pathlib

    root = pathlib.Path(gis_parcels.__file__).parent
    for name in ("gis_layer.py", "gis_match.py", "gis_parcels.py"):
        body = (root / name).read_text(encoding="utf-8").lower()
        for banned in ("a2gov", "a2mapseg", "seuqualifiedaddress", "a2arcgis"):
            assert banned not in body, f"{name} names {banned!r}"


# ── the report tells a run that examined nothing from one that found nothing ─


def test_every_count_is_reported_even_at_zero():
    result, _, _ = go()
    for key in ("city_rows", "premises_examined", "units_examined", "differences_found",
                "queued", "unmatched_ours", "city_rows_ignored", "thrash"):
        assert key in result["counts"], key


def test_ruling_eight_leaves_a_count_and_nothing_else():
    """A City address we have no premises for: *"c) ignore"*."""
    result, _, _ = go()
    assert result["counts"]["city_rows_ignored"] == 2
    assert all("09-01-300" not in str(one) for one in result["queue"])


def test_thrash_is_reported_because_it_is_our_bug_not_the_citys():
    ours = our_register()
    ours["premises"][0]["gis_parcel_id"] = "OLD-2"
    ours["premises"][0]["gis_parcel_id_was"] = "OLD-1"
    result, _, _ = go(ours=ours)
    assert result["counts"]["thrash"] == 1
    assert result["thrash_rows"] == ["P-00001"]


# ── F · the hand-off to runbook 20 (the "nothing fires it" item) ────────────


def test_an_apply_hands_the_landed_batch_to_runbook_twenty():
    """⚠ The build item hiding behind *"the runbook already exists"*.

    The runbook reads a landed batch and, with none, stops at step 1 saying
    *"Nothing has landed yet"*. This is the line that lands one.
    """
    started = []
    result, _, _ = go(mode=APPLY, hand_off=lambda key, batch: started.append((key, batch)) or True)
    assert result["handed_off"]["runbook"] == "gis_reconciliation"
    assert result["handed_off"]["started"] is True
    assert started[0][0] == "gis_reconciliation"
    assert started[0][1]["rows"] == 7, "the snapshot it actually pulled"


def test_a_preview_hands_off_nothing():
    """There is no landed batch to reconcile — a preview stored nothing."""
    started = []
    result, _, _ = go(mode=PREVIEW, hand_off=lambda key, batch: started.append(key) or True)
    assert result["handed_off"] == {}
    assert started == []


def test_a_stopped_run_hands_off_nothing():
    started = []
    result, _, _ = go(mode=APPLY, transport=fx.half_way_transport,
                      hand_off=lambda key, batch: started.append(key) or True)
    assert result["stopped"] is True
    assert started == []


def test_the_general_batch_landed_event_is_still_emitted_by_nothing():
    """⚠ **A HOLD WITH THE TEST THAT FIRES WHEN IT EXPIRES** (hard-won law 2).

    `gis_parcels` hands off to ONE runbook by name rather than emitting
    `batch.landed`, because seven runbooks name that event and a GIS pull is not
    the place to start six unrelated ones. **The day `CR-069` wave O emits it,
    this test goes red and names the hand-off that may then be removed** — a
    hold with no such test is a promise nobody is keeping.
    """
    import pathlib
    import re

    backend = pathlib.Path(gis_parcels.__file__).parents[2]
    emitters = []
    for path in backend.rglob("*.py"):
        if "migrations" in path.parts or path.name.startswith("test"):
            continue
        body = path.read_text(encoding="utf-8")
        for line in body.splitlines():
            if "batch.landed" not in line and "EVENT_BATCH_LANDED" not in line:
                continue
            # A docstring or comment SAYING it is not emitted is not an emitter,
            # and neither is the constant's own definition.
            stripped = line.strip()
            if stripped.startswith(("#", "*", '"', "'")) or "EVENT_BATCH_LANDED =" in stripped:
                continue
            if re.search(r"(emit|publish|dispatch|fire|send)\s*\(", stripped):
                emitters.append(f"{path.name}: {stripped}")
    assert emitters == [], (
        "`batch.landed` is now emitted — CR-069 wave O has landed. "
        "`seams/runbooks.hand_off_gis_batch` may now be replaced by the event, "
        "and the other six runbooks that name it should be considered together."
    )
