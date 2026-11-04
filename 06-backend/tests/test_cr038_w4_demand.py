# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007 (the published template + the row parser) ·
#           US-MET-008 (step-4 review dispositions — the bulk sibling) ·
#           US-MET-017 (one row per channel)   Screens: S28 · S25 · S29
# Rules:    BR-MET-051 (demand: a MANUAL demand-register value taken at the
#           cycle read, with the RESET NOTED — verbatim: *"Demand: manual
#           demand-register value at cycle read + reset noted; ratchet off
#           (BR-RAT proposal stands)"*, PO RD-4, CONFIRMED) ·
#           BR-MET-049 (the plan-driven expected register set: *"demand →
#           +demand record"*) · BR-MET-059 (the channel model) ·
#           BR-MET-032 (ONE published template, validate THEN accept — nothing
#           is coerced to make it fit) · BR-MET-062 (a missing demand value is
#           never estimated — a peak drives kW dollars) ·
#           CLAUDE.md hard rule 3 (a quantity never travels without its unit)
# CR:       CR-038 W4 — "complete DEMAND metering".
# ───────────────────────────────────────────────────────
"""CR-038 W4 — the demand reset, from the file to the committed read.

BR-MET-051's state before this lane was *"HALF — the field exists, the file
cannot carry it"*: `read_import_rows.demand_reset_noted` and
`meter_reads.demand_reset_noted` were both declared, `_post_row` already copied
one to the other, and NOTHING in the product ever set either. There was no
template column and no control.

The claim these tests defend: **a reset is never silently read as "no reset"**.
A blank column is an absence and stages `false`; a value nobody recognises is
REFUSED BY NAME and stages with its parse error attached — it never becomes
`false`, because a demand customer whose reset went unnoticed is mis-billed by
a whole cycle's peak.
"""

from decimal import Decimal

import pytest

from apps.metering import models, read_import, selectors, services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    accept_warnings,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# The W4 template header — the six published columns plus `demand_reset`.
DEMAND_HEADER = "meter_id,read_date,reading,channel,service,notes,demand_reset\n"


def demand_csv(*rows: str) -> str:
    return DEMAND_HEADER + "".join(r if r.endswith("\n") else r + "\n" for r in rows)


def rows_of(batch_id):
    return list(models.ReadImportRow.objects.filter(batch_id=batch_id).order_by("row_no"))


# ── Task 1 · the template column (BR-MET-032 + BR-MET-051) ─────────────────


def test_w4_tc1__the_published_template_carries_a_demand_reset_column():
    """BR-MET-051 + BR-MET-032: the ONE published template is the only place a
    file may declare a reset, so the column has to be IN it.

    RED (before this lane):
        AssertionError: assert 'demand_reset' in ('meter_id', 'read_date',
        'reading', 'channel', 'service', 'notes')
    """
    assert "demand_reset" in read_import.PUBLISHED_HEADERS
    assert "demand_reset" in read_import.OPTIONAL_TARGETS
    assert "demand_reset" not in read_import.REQUIRED_TARGETS  # optional by law
    header, example = read_import.template_csv().splitlines()[:2]
    assert header.split(",") == list(read_import.PUBLISHED_HEADERS)
    # the worked example row still has one cell per published column
    assert len(example.split(",")) == len(read_import.PUBLISHED_HEADERS)


@pytest.mark.parametrize("spelling", ["yes", "Yes", "Y", "true", "TRUE", "t", "1", "reset", "x"])
def test_w4_tc2__the_obvious_truthy_spellings_all_note_the_reset(spelling):
    """BR-MET-051: the value is written by a meter reader on a route sheet, so
    the spellings a human actually types are all accepted.

    RED (before this lane):
        AttributeError: 'ParsedRow' object has no attribute 'demand_reset'
    """
    parsed = read_import.parse_row(
        1,
        {
            "meter_id": "M-7001",
            "read_date": "2026-08-03",
            "reading": "412",
            "channel": "demand",
            "demand_reset": spelling,
        },
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    assert parsed.errors == []
    assert parsed.demand_reset is True


@pytest.mark.parametrize("spelling", ["no", "N", "false", "0", "f", "none", ""])
def test_w4_tc3__the_falsy_spellings_and_a_blank_cell_note_nothing(spelling):
    """An ABSENT column is an absence, not a claim — it stages `false`, which
    is what the column default has always meant.

    RED (before this lane):
        AttributeError: 'ParsedRow' object has no attribute 'demand_reset'
    """
    parsed = read_import.parse_row(
        1,
        {
            "meter_id": "M-7001",
            "read_date": "2026-08-03",
            "reading": "412",
            "channel": "demand",
            "demand_reset": spelling,
        },
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    assert parsed.errors == []
    assert parsed.demand_reset is False


def test_w4_tc4__an_unrecognised_reset_value_is_refused_by_name_never_read_as_false():
    """**The whole point of the column.** BR-MET-032 validate-THEN-accept: a
    value the parser does not recognise is kept VERBATIM with a named error,
    exactly like an unknown channel. Guessing `false` here would bill a demand
    customer against a register that had been zeroed.

    RED (before this lane):
        AssertionError: assert 'demand_reset_unrecognised' in []
    """
    parsed = read_import.parse_row(
        1,
        {
            "meter_id": "M-7001",
            "read_date": "2026-08-03",
            "reading": "412",
            "channel": "demand",
            "demand_reset": "maybe?",
        },
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    codes = [e["code"] for e in parsed.errors]
    assert read_import.ERR_DEMAND_RESET_UNKNOWN in codes
    assert read_import.ERR_DEMAND_RESET_UNKNOWN == "demand_reset_unrecognised"
    # kept verbatim next to the row — never snapped to a valid value
    detail = next(e for e in parsed.errors if e["code"] == read_import.ERR_DEMAND_RESET_UNKNOWN)
    assert detail["value"] == "maybe?"
    assert detail["field"] == "demand_reset"


def test_w4_tc5__a_reset_noted_on_a_non_demand_row_is_refused_by_name():
    """BR-MET-051 scopes the reset to the DEMAND register (`meter_reads.
    demand_reset_noted` has said "demand channel only" since it was declared).
    A reset noted against the energy register is a filled-in-wrong-column
    mistake, and the parser says so rather than storing a fact about a
    register that has no reset.

    RED (before this lane):
        AssertionError: assert 'demand_reset_not_demand_channel' in []
    """
    parsed = read_import.parse_row(
        1,
        {
            "meter_id": "M-7001",
            "read_date": "2026-08-03",
            "reading": "42864",
            "channel": "total",
            "demand_reset": "yes",
        },
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    codes = [e["code"] for e in parsed.errors]
    assert read_import.ERR_DEMAND_RESET_NOT_DEMAND in codes
    # ...and a `no` on a total row is not an error: it claims nothing.
    ok = read_import.parse_row(
        1,
        {
            "meter_id": "M-7001",
            "read_date": "2026-08-03",
            "reading": "42864",
            "channel": "total",
            "demand_reset": "no",
        },
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    assert ok.errors == []


def test_w4_tc6__the_column_auto_detects_by_its_aliases():
    """BR-MET-013: detection is by NAME against the published template, and the
    aliases are the ones a collector export actually emits.

    RED (before this lane):
        KeyError: 'demand_reset'
    """
    mapping = read_import.detect_mapping(
        ["meter_id", "read_date", "reading", "channel", "Demand Reset"]
    )
    assert mapping["demand_reset"] == "Demand Reset"
    assert read_import.missing_required(mapping) == []  # still optional


def test_w4_tc7__a_manual_grid_row_carries_the_reset_through_the_same_parser():
    """BR-MET-032 one code path: a typed row and an uploaded row are judged
    identically, the reset included.

    RED (before this lane):
        AttributeError: 'ParsedRow' object has no attribute 'demand_reset'
    """
    rows = read_import.parse_manual_rows(
        [
            {
                "meter_id": "M-7001",
                "read_date": "2026-08-03",
                "reading": "412",
                "channel": "demand",
                "demand_reset": "yes",
            }
        ]
    )
    assert rows[0].demand_reset is True


# ── Task 1 · the staged row and the committed read ─────────────────────────


def test_w4_tc8__staging_fills_the_field_the_row_already_carried(brazos, marcus):
    """BR-MET-051's "HALF" closed: `read_import_rows.demand_reset_noted` is
    written by the import, from the file.

    RED (before this lane):
        AssertionError: assert False is True
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(
            marcus,
            demand_csv(
                "M-7001,2026-08-03,42864,total,E,,",
                "M-7001,2026-08-03,412,demand,E,peak reset at read,yes",
            ),
        )
        staged = rows_of(batch["id"])
        assert [r.channel for r in staged] == ["total", "demand"]
        assert [r.demand_reset_noted for r in staged] == [False, True]
        # and the served row states it — a screen cannot show what is not served
        assert selectors.read_row_dict(staged[1])["demand_reset_noted"] is True


def test_w4_tc9__the_reset_reaches_the_committed_read(brazos, marcus):
    """`_post_row` has always copied `row.demand_reset_noted` onto the
    `meter_reads` row; nothing ever set the source. End to end now.

    RED (before this lane):
        AssertionError: assert False is True
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(
            marcus,
            demand_csv("M-7001,2026-08-03,412,demand,E,peak reset at read,yes"),
        )
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        read = models.MeterRead.objects.get(channel="demand")
        assert read.demand_reset_noted is True
        # hard rule 3 — the peak still travels with an EXPLICIT unit
        assert read.unit


# ── Task 2 · the bulk reset-noted control (BR-MET-051 · fleet read) ────────


def test_w4_tc10__one_row_can_be_noted_and_the_write_is_audited(brazos, marcus, audit_rows):
    """A clerk who learns of a reset at the review step records it there.

    RED (before this lane):
        AttributeError: module 'apps.metering.services' has no attribute
        'set_row_demand_reset'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, demand_csv("M-7001,2026-08-03,412,demand,E,,"))
        services.validate_read_batch(marcus, batch["id"])
        out = services.set_row_demand_reset(marcus, batch["id"], 1, {"noted": True})
        assert out["demand_reset_noted"] is True
        assert models.ReadImportRow.objects.get(batch_id=batch["id"]).demand_reset_noted is True
    assert "read_row.demand_reset" in [r["action"] for r in audit_rows]


def test_w4_tc11__a_non_demand_row_refuses_the_note(brazos, marcus):
    """The same scope as the parser (BR-MET-051, demand register only) — the
    server refuses regardless of what a screen offers.

    RED (before this lane):
        AttributeError: module 'apps.metering.services' has no attribute
        'set_row_demand_reset'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, demand_csv("M-7001,2026-08-03,42864,total,E,,"))
        services.validate_read_batch(marcus, batch["id"])
        with pytest.raises(errors.BizError):
            services.set_row_demand_reset(marcus, batch["id"], 1, {"noted": True})


def test_w4_tc12__the_bulk_control_notes_every_demand_row_and_reports_each(
    brazos, marcus, audit_rows
):
    """A fleet read on one visit means many rows share the reset — one click,
    and the answer says WHAT IT DID PER ROW rather than only how many.

    RED (before this lane):
        AttributeError: module 'apps.metering.services' has no attribute
        'bulk_demand_reset'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, asset_no="M-7001")
        a_meter(marcus, asset_no="M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = stage(
            marcus,
            demand_csv(
                "M-7001,2026-08-03,42864,total,E,,",
                "M-7001,2026-08-03,412,demand,E,,",
                "M-7002,2026-08-03,398,demand,E,,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        out = services.bulk_demand_reset(marcus, batch["id"], {"noted": True})
        assert out["noted"] == [2, 3]  # the two demand rows, by row_no
        assert [s["row_no"] for s in out["skipped"]] == [1]
        assert out["skipped"][0]["reason"] == "not_demand_channel"
        assert out["counts"] == {"noted": 2, "skipped": 1, "rows": 3}
        stored = {r.row_no: r.demand_reset_noted for r in rows_of(batch["id"])}
        assert stored == {1: False, 2: True, 3: True}
    # BR-MET-051 + CLAUDE.md rule 7: one audit row PER ROW, never one for the click
    noted = [r for r in audit_rows if r["action"] == "read_row.demand_reset"]
    assert len(noted) == 2


def test_w4_tc13__the_bulk_control_can_take_a_note_back(brazos, marcus):
    """`noted: false` is a correction of a mis-click, and it is the same
    recorded write — a staged row is not yet financially immutable
    (BR-MET-012: nothing has posted).

    RED (before this lane), on the staging half this depends on:
        assert False is True
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, demand_csv("M-7001,2026-08-03,412,demand,E,,yes"))
        services.validate_read_batch(marcus, batch["id"])
        assert rows_of(batch["id"])[0].demand_reset_noted is True
        services.bulk_demand_reset(marcus, batch["id"], {"noted": False})
        assert rows_of(batch["id"])[0].demand_reset_noted is False


def test_w4_tc14__a_posted_batch_refuses_the_note(brazos, marcus):
    """BR-MET-017 / hard rule 4: a committed read is not edited from the
    review step, and neither is the staged row behind it.

    RED (before this lane):
        AttributeError: module 'apps.metering.services' has no attribute
        'bulk_demand_reset'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, demand_csv("M-7001,2026-08-03,412,demand,E,,"))
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        with pytest.raises(errors.BizError):
            services.bulk_demand_reset(marcus, batch["id"], {"noted": True})


# ── Task 3 · the peak is not energy (CLAUDE.md hard rule 3) ────────────────


def test_w4_tc15__a_demand_read_is_served_marked_as_a_peak_with_its_unit(brazos, marcus):
    """kW is not kWh. Every surface that renders a read quantity has to be able
    to tell a PEAK from an energy total without re-deriving anything
    (BR-MET-056), so `read_dict` states the register kind on the row.

    RED (before this lane):
        KeyError: 'is_peak'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(
            marcus,
            demand_csv(
                "M-7001,2026-08-03,42864,total,E,,",
                "M-7001,2026-08-03,412,demand,E,,yes",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        served = {
            r.channel: selectors.read_dict(r) for r in models.MeterRead.objects.all()
        }
    assert served["demand"]["is_peak"] is True
    assert served["total"]["is_peak"] is False
    # hard rule 3: neither quantity is ever served without its unit
    for row in served.values():
        assert row["unit"]
        if row["consumption"] is not None:
            assert row["usage_display"].endswith(row["unit"])


def test_w4_tc16__the_peak_states_that_its_unit_is_the_meters_energy_uom(brazos, marcus):
    """⚠ **AMENDED 2026-08-27 — SUPERSEDED (PO ruling closing OQ-391 →
    BR-MET-143). The assertion is INVERTED and the test is kept in place, not
    deleted**, because the day it goes red is exactly what its own docstring
    said it was waiting for.

    What it said, verbatim, when the CR-038 W4 lane wrote it: *"No signed rule
    says what unit a demand-channel read carries, so this lane will not invent
    one … This test PINS the mismatch so the day a rule states the demand UoM,
    it goes red here and nowhere else."* That day is 2026-08-27. PO verbatim:
    *"A demand reading carries kW - we have to match utility service unit and
    meter reading unit - if it does not match then we have intriduce multiplier
    factor on meter. you will ahve to seed that data."*

    So the peak now carries **kW** — the REGISTER's unit, not the meter's —
    while the energy register on the same meter still carries kWh. The lane
    that pinned the mismatch was right to pin it and right not to invent kW;
    the invention is now a ruling.

    RED (before the BR-MET-143 lane):
        AssertionError: assert 'kWh' == 'kW'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, uom="kWh")
        batch = stage(marcus, demand_csv("M-7001,2026-08-03,412,demand,E,,yes"))
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        served = selectors.read_dict(models.MeterRead.objects.get(channel="demand"))
    assert served["is_peak"] is True
    # BR-MET-143: the DEMAND REGISTER's own unit, on a meter whose energy
    # register reads kWh. This line asserted `"kWh"` until 2026-08-27.
    assert served["unit"] == "kW"
    assert served["demand_reset_noted"] is True


def test_w4_tc17__a_peak_and_an_energy_total_are_never_summed(brazos, marcus):
    """CLAUDE.md hard rule 3, stated as arithmetic: 42,864 kWh of energy and a
    412 peak are two quantities about two different things, and no served
    figure adds them.

    This is the assertion that would have caught the monthly-usage defect this
    lane REPORTS: `monthly_usage_service._reads_by_service` filters on nothing
    but the lineage head, so every channel a meter records lands in one Σ.

    RED (before this lane):
        KeyError: 'is_peak'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(
            marcus,
            demand_csv(
                "M-7001,2026-08-03,42864,total,E,,",
                "M-7001,2026-08-03,412,demand,E,,",
            ),
        )
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        served = [selectors.read_dict(r) for r in models.MeterRead.objects.all()]
    peaks = [r for r in served if r["is_peak"]]
    energy = [r for r in served if not r["is_peak"]]
    assert len(peaks) == 1 and len(energy) == 1
    # Each row is its own quantity and carries its own unit — nothing anywhere
    # in what is served composes a figure out of the two.
    assert peaks[0]["current_value"] == "412.000000"
    assert energy[0]["current_value"] == "42864.000000"
    assert peaks[0]["unit"] and energy[0]["unit"]  # hard rule 3, both rows
    combined = Decimal(peaks[0]["current_value"]) + Decimal(energy[0]["current_value"])
    assert str(combined) not in [str(v) for row in served for v in row.values()]


# ── BR-MET-049 · the expected-set resolver is REUSED, never re-derived ─────


def test_w4_tc18__the_demand_expected_set_comes_from_the_one_resolver():
    """BR-MET-049 verbatim: *"demand → +demand record"*. W1 landed that in
    `completeness.PlanRegisterResolver`; this lane calls it and writes no
    second copy of the rule.

    RED: n/a — this test is a REGRESSION FENCE on the reuse, and it passed the
    moment it was written. It is here so a later lane that re-derives the set
    inside `read_import` breaks a test that names the duplication.
    """
    from apps.metering import completeness

    source = (completeness.__file__, "PlanRegisterResolver")
    assert hasattr(completeness, source[1])
    # the demand branch lives in completeness and nowhere else
    import inspect

    body = inspect.getsource(completeness.PlanRegisterResolver._derive_plan_set)
    assert 'model == "demand"' in body
    assert "CHANNEL_DEMAND" in body
    ri = inspect.getsource(read_import)
    assert 'model == "demand"' not in ri  # no second implementation of BR-MET-049


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W4 (BR-MET-051 · BR-MET-049 · CLAUDE.md hard rule 3)
# generated: 2026-08-26 by the CR-038 W4 demand lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
