# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — `POST work/mobile/reads/sync` (07-endpoints.md N1),
#           the turn-in (N6) and the can't-read reasons (N12).
# Story:    US-FLD-040 (1,000 readings in 20 batches, two retried, nothing lost
#           or doubled) · US-FLD-041 · US-FLD-042 · US-FLD-059 (out of range
#           accepted and flagged) · US-FLD-060 (eight seeded, tenant-extensible)
#           · US-FLD-061 (a meter not on the route; a different meter; a meter
#           added in the field) · US-FLD-063 … US-FLD-066
# Rules:    BR-FLD-00080 … 00097 · BR-WRK-063 (SUPERSEDED for field items
#           2026-10-21 — PO *"back to the technician"*: what cannot post is
#           REFUSED with its reason and stores nothing) · BR-MET-129 ·
#           CLAUDE.md hard rules 1, 3, 6
# Tests:    this file (SQLite) · tests/test_cr187_reads_pg.py (law 14)
# ───────────────────────────────────────────────────────
"""The sync door, end to end through the real read pipeline.

RED FIRST (hard-won law 7, in pytest): at the commit before this lane every
case here fails on `ImportError: cannot import name 'field_reads'`.

⚠ **FLIPPED 2026-10-21.** Every case that asserted `held_for_review` (stored
and flagged for the office) now asserts `refused` with the same reason, a
message key, NOTHING stored, and — `test_a_refused_reading_fixed_and_resent_*`
— that the fixed item posts once. PO, verbatim: *"back to the technician"*.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import field_reads, field_routes
from apps.metering import models as metering_models
from apps.metering.field_read_models import (
    CantReadReason,
    FieldMeterProposal,
    FieldRead,
    FieldRouteTurnIn,
)
from core import errors

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import (
    LAST_DIAL,
    a_cant_read,
    a_reading,
    build_route,
    captured,
    reader_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _reads(asset_id, source="manual"):
    return metering_models.MeterRead.objects.filter(asset_id=asset_id, source=source)


def _results(out):
    return [item["result"] for item in out["items"]]


def _refused(receipt, reason):
    """Back to the reader (2026-10-21): refused, its reason and key, nothing
    stored under its key."""
    assert receipt["result"] == "refused", receipt
    assert receipt["reason"] == reason, receipt
    assert receipt["message_key"] == f"work.mobile.reads.{reason}", receipt
    assert receipt["detail"]["reason"] == reason
    assert not FieldRead.objects.filter(key=receipt["key"]).exists(), "a refused item was stored"


@pytest.fixture()
def fresh_world(brazos, dana):
    """The same route with NO history — for the volume run, whose 250 capture
    days would otherwise interleave with twelve months already on file."""
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader, history=False)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


# ══════════════════════════════════════════════════════════════════════════
# A reading posts through the ONE pipeline, with its unit and its evidence
# ══════════════════════════════════════════════════════════════════════════
def test_a_reading_posts_as_a_meter_read_with_the_registers_unit(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader, {"items": [a_reading("ray-0001", "MTR-0471", "48400", route_id=w.route_id)]}
        )
        assert _results(out) == ["accepted"], out
        receipt = out["items"][0]
        assert receipt["outcome"] == "posted"
        assert receipt["off_route"] is False
        read = metering_models.MeterRead.objects.get(id=receipt["meter_read_id"])
        # Hard rule 3 — the REGISTER's unit lands on the read, and the
        # consumption is measured from the last committed head.
        assert read.unit == "kWh"
        assert read.current_value == Decimal("48400")
        assert read.consumption == Decimal("48400") - LAST_DIAL
        assert read.source == "manual"
        # The reader is the user the read is attributed to (R88 — who read it).
        assert read.imported_by_id == reader.id
        # R96 — the engine's verdict travels beside the reader's, never merged.
        assert receipt["engine"]["status"] == read.status
        assert receipt["engine"]["unit"] == "kWh"

        row = FieldRead.objects.get(key="ray-0001")
        assert row.reader_status == "read"
        assert row.meter_read_id == read.id
        assert row.lat == Decimal("29.785100") and row.accuracy_m == Decimal("4.00")
        assert row.device_captured_at is not None and row.received_at is not None  # R92
        assert row.identified_by == "scan"
        assert row.remark_source == "voice"


def test_a_reading_with_no_unit_is_never_assumed_it_goes_back(world):
    """Hard rule 3 — never assume. Refused back to the reader, never posted."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        item = a_reading("ray-0002", "MTR-0471", "48400", route_id=w.route_id)
        del item["unit"]
        out = field_reads.sync_reads(reader, {"items": [item]})
        _refused(out["items"][0], field_reads.HELD_UNIT_MISSING)
        assert out["refused"] == 1 and out["held_for_review"] == 0
        assert not _reads(w.meters["MTR-0471"]["id"]).exists()


def test_a_refused_reading_fixed_and_resent_posts_once_under_either_key(world):
    """Idempotency still holds across a refusal: nothing was stored, so the
    SAME key resent fixed posts once; a resend of that again is a duplicate;
    and a fixed item under a NEW key also posts once."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        bad = a_reading("ray-0006", "MTR-0471", "48400", route_id=w.route_id, unit="gal")
        assert _results(field_reads.sync_reads(reader, {"items": [bad]})) == ["refused"]
        fixed = a_reading("ray-0006", "MTR-0471", "48400", route_id=w.route_id)
        assert _results(field_reads.sync_reads(reader, {"items": [fixed]})) == ["accepted"]
        assert _results(field_reads.sync_reads(reader, {"items": [fixed]})) == ["duplicate"]
        assert _reads(w.meters["MTR-0471"]["id"]).count() == 1

        bad2 = a_reading("ray-0007", "MTR-0472", "48390", route_id=w.route_id, unit="gal")
        assert _results(field_reads.sync_reads(reader, {"items": [bad2]})) == ["refused"]
        new_key = a_reading("ray-0008", "MTR-0472", "48390", route_id=w.route_id)
        assert _results(field_reads.sync_reads(reader, {"items": [new_key]})) == ["accepted"]
        assert _reads(w.meters["MTR-0472"]["id"]).count() == 1


def test_a_refusal_leaves_an_audit_row_naming_the_key_and_reason(world, monkeypatch):
    """Nothing stores a refused item, so the sync's audit row is the record."""
    seen = []
    real = field_reads.core_audit.write_row

    def recording(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(field_reads.core_audit, "write_row", recording)
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        bad = a_reading("ray-0009", "MTR-0471", "48400", route_id=w.route_id, unit="gal")
        field_reads.sync_reads(reader, {"items": [bad]})
    row = [r for r in seen if r["action"] == "field_reads.synced"][-1]
    assert row["after"]["refused_items"] == [
        {"key": "ray-0009", "reason": field_reads.HELD_UNIT_NOT_REGISTERS}
    ]


def test_a_reading_in_the_wrong_unit_goes_back_with_both_units_named(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader,
            {"items": [a_reading("ray-0003", "MTR-0471", "48400", route_id=w.route_id, unit="gal")]},
        )
        receipt = out["items"][0]
        _refused(receipt, field_reads.HELD_UNIT_NOT_REGISTERS)
        assert receipt["detail"]["params"] == {"register_unit": "kWh", "stated_unit": "gal"}
        assert not _reads(w.meters["MTR-0471"]["id"]).exists()


# ══════════════════════════════════════════════════════════════════════════
# R80 / R11 — out of range is WARNED and ACCEPTED, and flagged for the office
# ══════════════════════════════════════════════════════════════════════════
def test_out_of_range_is_accepted_and_flagged(world):
    """71,400 against a last dial of 47,700 is 23,700 kWh — over thirty times
    the 700 kWh month. It posts, flagged HIGH; the reader's accepted-anyway is
    kept beside the engine's verdict."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader,
            {
                "items": [
                    a_reading(
                        "ray-0004", "MTR-0471", "71400", route_id=w.route_id, accepted_anyway=True
                    )
                ]
            },
        )
        receipt = out["items"][0]
        assert receipt["result"] == "accepted", out
        assert receipt["outcome"] == "posted"
        assert "high" in receipt["engine"]["flags"]
        read = metering_models.MeterRead.objects.get(id=receipt["meter_read_id"])
        assert read.status == "high"
        assert read.disposition == "accept_with_flag"
        assert FieldRead.objects.get(key="ray-0004").accepted_anyway is True


def test_a_reading_below_the_last_one_is_accepted_with_its_flag(world):
    """R81 — a reading below the previous one. ⚠ **SUPERSEDED 2026-10-31
    (FB-022, DEF-MET-10797).** This test asserted the 2026-10-21 ruling — the
    field door REFUSED it back with the engine's rule named. PO 2026-10-31,
    verbatim: *"if the current reading is less than previous reading it shows
    warning to technician , but do not refuse the reading accept"*. It is now
    stored and posted with its `negative_usage` flag and NO consumption
    (BR-MET-052 never invents one), so billing meets it as a reading to be
    checked (`read_flagged`) until a clerk corrects it."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader, {"items": [a_reading("ray-0005", "MTR-0471", "41000", route_id=w.route_id)]}
        )
        receipt = out["items"][0]
        assert receipt["result"] == "accepted", receipt
        read = metering_models.MeterRead.objects.get(id=receipt["meter_read_id"])
        assert (read.current_value, read.status, read.consumption) == (
            Decimal("41000"),
            "negative_usage",
            None,
        )


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 6 — idempotent on the key minted at capture
# ══════════════════════════════════════════════════════════════════════════
def test_a_resent_batch_is_all_duplicates_and_adds_nothing(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        batch = {
            "items": [
                a_reading("ray-0010", "MTR-0471", "48400", route_id=w.route_id),
                a_reading("ray-0011", "MTR-0472", "48390", route_id=w.route_id),
            ]
        }
        first = field_reads.sync_reads(reader, batch)
        again = field_reads.sync_reads(reader, batch)
        assert _results(first) == ["accepted", "accepted"]
        assert _results(again) == ["duplicate", "duplicate"]
        assert again["items"][0]["first"]["outcome"] == "posted"
        assert _reads(w.meters["MTR-0471"]["id"]).count() == 1
        assert _reads(w.meters["MTR-0472"]["id"]).count() == 1


def test_a_key_repeated_inside_one_batch_counts_once(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        item = a_reading("ray-0012", "MTR-0471", "48400", route_id=w.route_id)
        out = field_reads.sync_reads(reader, {"items": [item, dict(item)]})
        assert _results(out) == ["accepted", "duplicate"]
        assert out["items"][1]["first"]["outcome"] == "posted"
        assert _reads(w.meters["MTR-0471"]["id"]).count() == 1


def test_an_item_with_no_key_is_refused_and_the_rest_land(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        keyless = a_reading("x", "MTR-0472", "48390", route_id=w.route_id)
        del keyless["key"]
        out = field_reads.sync_reads(
            reader,
            {"items": [keyless, a_reading("ray-0013", "MTR-0471", "48400", route_id=w.route_id)]},
        )
        assert _results(out) == ["refused", "accepted"]
        assert out["items"][0]["reason"] == "key_required"


def test_more_than_fifty_items_is_refused_whole_before_anything_is_stored(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        items = [
            a_reading(f"ray-big-{n}", "MTR-0471", "48400", route_id=w.route_id) for n in range(51)
        ]
        with pytest.raises(errors.ValidationError):
            field_reads.sync_reads(reader, {"items": items})
        assert not FieldRead.objects.filter(key__startswith="ray-big-").exists()


# ══════════════════════════════════════════════════════════════════════════
# R82 — the can't-read reasons are DATA: eight seeded, tenant-extensible
# ══════════════════════════════════════════════════════════════════════════
def test_eight_reasons_are_seeded_in_the_boards_order(world):
    with tenant_ctx(world["tenant"]):
        listed = field_reads.cant_read_reasons()
        assert listed["count"] == 8
        assert [row["name"] for row in listed["results"]] == [
            "Dog",
            "Locked",
            "No access",
            "Buried or covered",
            "Obstructed",
            "Meter not found",
            "Unsafe",
            "Illegible",
        ]
        # Idempotent: asking again seeds nothing more.
        field_reads.ensure_cant_read_reasons()
        assert CantReadReason.objects.filter(tenant_id=world["tenant"].id).count() == 8


def test_a_utility_adds_its_own_reason_and_a_reader_can_use_it(world):
    reader, w, admin = world["reader"], world["route"], world["admin"]
    with tenant_ctx(world["tenant"]):
        field_reads.add_cant_read_reason(admin, {"code": "flooded", "name": "Flooded pit"})
        assert field_reads.cant_read_reasons()["count"] == 9
        out = field_reads.sync_reads(
            reader, {"items": [a_cant_read("ray-0020", "MTR-0472", "flooded", route_id=w.route_id)]}
        )
        assert out["items"][0]["result"] == "accepted"
        assert out["items"][0]["outcome"] == "recorded"
        row = FieldRead.objects.get(key="ray-0020")
        assert row.cant_read_reason == "flooded"
        assert row.value is None
        # No reading is invented for a could-not-read (BR-MET-028 — a null
        # register value would read as an estimate nobody made).
        assert not metering_models.MeterRead.objects.filter(
            asset_id=w.meters["MTR-0472"]["id"], source="manual"
        ).exists()


def test_a_deactivated_reason_is_not_offered_and_a_reading_using_it_goes_back(world):
    reader, w, admin = world["reader"], world["route"], world["admin"]
    with tenant_ctx(world["tenant"]):
        field_reads.set_cant_read_reason_active(admin, "dog", {"active": False})
        assert "dog" not in [row["code"] for row in field_reads.cant_read_reasons()["results"]]
        assert field_reads.cant_read_reasons(include_inactive=True)["count"] == 8
        out = field_reads.sync_reads(
            reader, {"items": [a_cant_read("ray-0021", "MTR-0472", "dog", route_id=w.route_id)]}
        )
        _refused(out["items"][0], field_reads.HELD_REASON_UNKNOWN)


def test_a_duplicate_reason_code_is_refused_case_insensitively(world):
    with tenant_ctx(world["tenant"]):
        with pytest.raises(errors.ValidationError):
            field_reads.add_cant_read_reason(world["admin"], {"code": "DOG", "name": "Dog again"})


# ══════════════════════════════════════════════════════════════════════════
# RW-18 · RW-19 · RW-20 — what does not fit the list
# ══════════════════════════════════════════════════════════════════════════
def test_off_route_is_accepted_and_marked(world):
    """R84 — MTR-0533 is at 1206 Maple, on no route. The reading is real."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader, {"items": [a_reading("ray-0030", "MTR-0533", "48300", route_id=w.route_id)]}
        )
        receipt = out["items"][0]
        assert receipt["result"] == "accepted" and receipt["outcome"] == "posted", out
        assert receipt["off_route"] is True
        row = FieldRead.objects.get(key="ray-0030")
        assert row.off_route is True
        # The stop is resolved from the meter's own premises when not sent.
        assert str(row.premises_id) == str(w.off_premises)


def test_a_different_meter_is_never_guessed(world):
    """RW-18 — the list says MTR-0471, the reader scanned MTR-0533. With no
    answer the reading goes BACK to the reader, posted against neither."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader,
            {
                "items": [
                    a_reading(
                        "ray-0031",
                        "MTR-0533",
                        "48300",
                        route_id=w.route_id,
                        expected_meter_no="MTR-0471",
                    )
                ]
            },
        )
        _refused(out["items"][0], field_reads.HELD_DIFFERENT_METER)
        assert not _reads(w.meters["MTR-0533"]["id"]).exists()
        assert not _reads(w.meters["MTR-0471"]["id"]).exists()


def test_swapped_with_a_plate_photo_posts_against_the_meter_actually_read(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader,
            {
                "items": [
                    a_reading(
                        "ray-0032",
                        "MTR-0533",
                        "48300",
                        route_id=w.route_id,
                        expected_meter_no="MTR-0471",
                        mismatch_answer="swapped",
                        photos=["ph-0032"],
                    ),
                    a_reading(
                        "ray-0033",
                        "MTR-0533",
                        "48300",
                        route_id=w.route_id,
                        expected_meter_no="MTR-0472",
                        mismatch_answer="cannot_tell",
                        photos=["ph-0033"],
                    ),
                ]
            },
        )
        assert _results(out) == ["accepted", "refused"], out
        _refused(out["items"][1], field_reads.HELD_METER_UNCERTAIN)
        row = FieldRead.objects.get(key="ray-0032")
        assert str(row.asset_id) == w.meters["MTR-0533"]["id"]
        assert str(row.expected_asset_id) == w.meters["MTR-0471"]["id"]
        assert _reads(w.meters["MTR-0533"]["id"]).count() == 1


def test_swapped_without_the_plate_photo_goes_back(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader,
            {
                "items": [
                    a_reading(
                        "ray-0034",
                        "MTR-0533",
                        "48300",
                        route_id=w.route_id,
                        expected_meter_no="MTR-0471",
                        mismatch_answer="swapped",
                    )
                ]
            },
        )
        _refused(out["items"][0], field_reads.HELD_PLATE_PHOTO)


def test_a_scan_matching_nothing_goes_back_and_is_never_resolved_to_a_plausible_meter(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        item = a_reading("ray-0035", "x", "48300", route_id=w.route_id)
        del item["meter_no"]
        item["scanned_code"] = "90241"
        out = field_reads.sync_reads(reader, {"items": [item]})
        _refused(out["items"][0], field_reads.HELD_METER_NOT_FOUND)


def test_a_meter_added_in_the_field_is_pending_and_its_reading_waits(world):
    """R85 — *"It can be read immediately; it bills only once accepted."* No
    assets row is created; the reading is kept against the PROPOSAL and no
    `meter_reads` row exists until the office accepts the meter."""
    reader, w = world["reader"], world["route"]
    Asset = __import__("django.apps", fromlist=["apps"]).apps.get_model("assets", "Asset")
    with tenant_ctx(world["tenant"]):
        assets_before = Asset.objects.count()
        reads_before = metering_models.MeterRead.objects.count()
        add = {
            "key": "ray-0040",
            "kind": "add_meter",
            "route_id": str(w.route_id),
            "premises_id": str(w.premises[0]),
            "photos": ["ph-0040"],
            "captured_at": captured(),
            "meter": {"badge": "90241", "service": "electric", "size_class": None,
                      "unit_of_measure": "kWh"},
        }
        reading = a_reading("ray-0041", "unused", "120", route_id=w.route_id, proposal_key="ray-0040")
        del reading["meter_no"]
        out = field_reads.sync_reads(reader, {"items": [add, reading]})
        assert _results(out) == ["accepted", "accepted"], out
        assert [i["outcome"] for i in out["items"]] == ["awaiting_acceptance"] * 2
        proposal = FieldMeterProposal.objects.get(key="ray-0040")
        assert proposal.status == "pending"
        assert str(proposal.premises_id) == str(w.premises[0])
        assert FieldRead.objects.get(key="ray-0041").proposal_id == proposal.id
        # Bills nothing by construction: no asset, no reading.
        assert Asset.objects.count() == assets_before
        assert metering_models.MeterRead.objects.count() == reads_before


def test_a_field_meter_with_no_photograph_goes_back_not_proposed(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        add = {
            "key": "ray-0042",
            "kind": "add_meter",
            "premises_id": str(w.premises[0]),
            "captured_at": captured(),
            "meter": {"badge": "90241", "service": "electric"},
        }
        out = field_reads.sync_reads(reader, {"items": [add]})
        _refused(out["items"][0], field_reads.HELD_PROPOSAL_INCOMPLETE)
        assert out["items"][0]["detail"]["params"]["missing"] == ["photos"]
        assert not FieldMeterProposal.objects.filter(key="ray-0042").exists()


def test_an_unknown_kind_goes_back_and_stays_on_the_phone(world):
    reader = world["reader"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader, {"items": [{"key": "ray-0050", "kind": "note", "text": "gate open"}]}
        )
        _refused(out["items"][0], field_reads.HELD_UNKNOWN_KIND)
        assert out["items"][0]["detail"]["params"] == {"kind": "note"}


# ══════════════════════════════════════════════════════════════════════════
# RW-25 … RW-27 — turning in is not a gate; the receipt names what landed
# ══════════════════════════════════════════════════════════════════════════
def test_turn_in_names_what_landed_what_did_not_and_closes_nothing(world):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        field_reads.sync_reads(
            reader,
            {
                "items": [
                    a_reading("ray-0060", "MTR-0471", "48400", route_id=w.route_id),
                    a_reading("ray-0061", "MTR-0472", "71400", route_id=w.route_id,
                              accepted_anyway=True),
                    a_cant_read("ray-0062", "MTR-0473", "dog", route_id=w.route_id),
                    # A scan that matches nothing — refused back, and visits no
                    # meter; the server holds nothing for it, so the turn-in
                    # names it as NOT RECEIVED (the phone still has it).
                    {**a_reading("ray-0063", "x", "120", route_id=w.route_id),
                     "meter_no": None, "scanned_code": "90241"},
                ]
            },
        )
        receipt = field_reads.turn_in(
            reader,
            w.route_id,
            {"key": "turn-1", "keys": ["ray-0060", "ray-0061", "ray-0062", "ray-0063", "ray-0064"],
             "counts": {"taken": 3}},
        )
        assert receipt["closes_cycle"] is False
        assert receipt["landed"]["readings"] == 2
        assert receipt["landed"]["with_reason"] == 1
        # The engine flags BOTH posted readings (the units are vacant —
        # `vacant_unit` — and 71,400 is also HIGH); the reader took one anyway.
        assert receipt["landed"]["flagged"] == 2
        assert receipt["landed"]["accepted_anyway"] == 1
        assert receipt["held"]["count"] == 0
        assert receipt["not_received"] == {"count": 2, "keys": ["ray-0063", "ray-0064"]}
        # MTR-0474 was never touched — the office's chase list.
        assert receipt["never_read"] == {"meters": 1, "of": 4}
        # Idempotent on its key; the window and cycle are untouched.
        again = field_reads.turn_in(reader, w.route_id, {"key": "turn-1"})
        assert again["turned_in_at"] == receipt["turned_in_at"]
        assert FieldRouteTurnIn.objects.filter(key="turn-1").count() == 1
        assert not metering_models.ReadWindow.objects.filter(route_id=w.route_id).exists()


def test_another_readers_route_is_a_404_for_a_technician(world, brazos):
    w = world["route"]
    with tenant_ctx(brazos):
        stranger = reader_actor(brazos, email="other.reader@brazosbendutilities.test")
        with pytest.raises(errors.NotFoundError):
            field_reads.turn_in(stranger, w.route_id, {"key": "turn-x"})
        with pytest.raises(errors.NotFoundError):
            field_routes.route_page(stranger, w.route_id)


# ══════════════════════════════════════════════════════════════════════════
# US-FLD-040 — 1,000 readings in 20 batches of 50, two batches retried,
# nothing lost and nothing doubled (E2E-03: "exactly 1,000 — not 1,048 from
# the re-sent batches, not 963")
# ══════════════════════════════════════════════════════════════════════════
def test_a_thousand_readings_in_twenty_batches_two_retried_land_exactly_once(fresh_world):
    """One reading per day per meter is the real shape; 1,000 readings over the
    route's four meters is therefore spread over 250 consecutive capture DAYS,
    each a higher dial than the last, so every one is a lawful reading and the
    count at the far end is the test."""
    world = fresh_world
    reader, w = world["reader"], world["route"]
    meters = ["MTR-0471", "MTR-0472", "MTR-0473", "MTR-0474"]
    with tenant_ctx(world["tenant"]):
        items = []
        for n in range(1000):
            meter = meters[n % 4]
            day = n // 4  # 0 … 249
            items.append(
                a_reading(
                    f"ray-k{n:04d}",
                    meter,
                    str(LAST_DIAL + 23 * (day + 1)),
                    route_id=w.route_id,
                    captured_at=captured(day_offset=day - 249),
                )
            )
        batches = [items[i : i + 50] for i in range(0, 1000, 50)]
        answers = []
        for index, batch in enumerate(batches):
            answers.append(field_reads.sync_reads(reader, {"items": batch}))
            if index in (6, 13):
                # The connection dropped after the server committed: the
                # handset never saw the answer and sends the same batch again.
                answers.append(field_reads.sync_reads(reader, {"items": batch}))
        accepted = sum(a["accepted"] for a in answers)
        duplicates = sum(a["duplicate"] for a in answers)
        held = sum(a["held_for_review"] + a["refused"] for a in answers)
        assert held == 0, [i for a in answers for i in a["items"] if i["result"] != "accepted"][:3]
        assert (accepted, duplicates) == (1000, 100)
        assert FieldRead.objects.filter(key__startswith="ray-k").count() == 1000
        posted = metering_models.MeterRead.objects.filter(
            asset_id__in=[w.meters[m]["id"] for m in meters], source="manual"
        )
        assert posted.count() == 1000
        # Twenty batches staged, not a thousand and not twenty-two.
        assert (
            metering_models.ReadImportBatch.objects.filter(
                session_ref="field_app_route_reads"
            ).count()
            == 20
        )


# ══════════════════════════════════════════════════════════════════════════
# CLAUDE.md hard rule 1 — tenant isolation
# ══════════════════════════════════════════════════════════════════════════
def test_another_tenants_meter_and_route_are_invisible(world, lonestar, erin):
    reader, w = world["reader"], world["route"]
    with tenant_ctx(lonestar):
        field_reads.ensure_cant_read_reasons()
        lone_reader = reader_actor(lonestar, email="lone.reader@lsrwater.test")
        # Brazos' meter number and route, sent from Lone Star's session.
        out = field_reads.sync_reads(
            lone_reader,
            {"items": [a_reading("lsr-0001", "MTR-0471", "48400", route_id=w.route_id, unit="kWh")]},
        )
        # Another tenant's meter never resolves: refused back, nothing stored.
        assert out["items"][0]["result"] == "refused"
        assert out["items"][0]["reason"] == field_reads.HELD_METER_NOT_FOUND
        assert not FieldRead.objects.filter(key="lsr-0001", tenant_id=lonestar.id).exists()
        with pytest.raises(errors.NotFoundError):
            field_routes.route_page(erin, w.route_id)
        assert field_routes.my_routes(lone_reader)["count"] == 0
        assert field_reads.cant_read_reasons()["count"] == 8
    with tenant_ctx(world["tenant"]):
        # The SAME key in another tenant is another item — keys are per tenant.
        out = field_reads.sync_reads(
            reader, {"items": [a_reading("lsr-0001", "MTR-0471", "48400", route_id=w.route_id)]}
        )
        assert out["items"][0]["result"] == "accepted"
        # Every app read is scoped by tenant (on PostgreSQL RLS FORCE scopes it
        # too; the suite's SQLite has no RLS, so the filter is explicit here).
        assert FieldRead.objects.filter(
            key="lsr-0001", tenant_id=world["tenant"].id
        ).count() == 1


def test_captured_after_now_is_still_judged_by_the_pipeline_never_by_this_door(world):
    """R92 — the device clock is a fact about the device. A clock running a
    day fast is not refused here; it is the read pipeline's call."""
    reader, w = world["reader"], world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            reader,
            {"items": [a_reading("ray-0070", "MTR-0474", "48400", route_id=w.route_id,
                                 captured_at=captured(day_offset=1))]},
        )
        # Either the pipeline posted it, or it went back to the reader with the
        # pipeline's own reason — never this door's judgment of the clock.
        assert out["items"][0]["result"] in ("accepted", "refused")
        if out["items"][0]["result"] == "refused":
            assert out["items"][0]["reason"] == field_reads.HELD_PIPELINE_ERROR


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-040@fa5746815 (CR-187-BRC10 route-reading server lane)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no frontend in this lane) F✔ G✔ H=deferred(no 🔒 path in a test)
# gates: see the lane report
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
