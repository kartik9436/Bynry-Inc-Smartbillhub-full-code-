# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 task 12 — MQ-033 read formats on the PHONE. This
#           file locks the handset's copy of the wire to the server.
# Rules:    BR-MET-1212 · BR-MET-1214 · BR-MET-1215 · BR-MET-1216
# Tests:    this file · field-app/tests/sync/readFormats.test.ts (the handset)
# ───────────────────────────────────────────────────────
"""The read-format SHAPE the phone's tests are built from is the shape this
server sends — and the reading the phone builds is one this server stores
without an issue.

`field-app/tests/sync/support/serverReadFormat.json` is the handset's copy of
one resolved route format, one published version with its questions, one
reading item as the phone sends it, and the receipt's `answers` block. The
phone's tests download from that file and assert their outbox item EQUALS its
`reading_item`. This file builds a real format and a real route, compares KEY
SETS with the file, then sends the file's `reading_item` through the real sync
door. DEF-FLD-10582's lesson (MQ-015): handset tests that never meet the wire
drift onto a shape the server never sends, and every test stays green.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from apps.metering import field_reads, field_routes, read_formats
from apps.metering.read_format_models import ReadFormat

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import build_route, reader_actor, tenant_ctx

pytestmark = pytest.mark.django_db

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "field-app" / "tests" / "sync" / "support" / "serverReadFormat.json"
)


def _fixture():
    return json.loads(FIXTURE.read_text())


def _world(brazos, dana):
    """The fixture's six questions, published and pointed at from the cycle."""
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader, history=False)
        fid = read_formats.create_format(dana, {"name": "Electric walk", "service": "electric"})["id"]
        for q in _fixture()["version"]["questions"]:
            body = {
                k: q[k]
                for k in ("label", "help_text", "data_type", "options", "is_required", "asked_when", "show_if")
                if q[k] is not None
            }
            read_formats.add_question(dana, fid, body)  # the key is derived from the label, as the fixture names it
        read_formats.publish(dana, fid)
        read_formats.set_cycle_format(dana, route.cycle_id, {"read_format_id": fid})
        version_id = str(ReadFormat.objects.get(pk=fid).current_version_id)
        page = field_routes.route_page(reader, route.route_id)
    return {"tenant": brazos, "reader": reader, "route": route, "version_id": version_id, "page": page}


def _keys(d):
    return sorted(d.keys())


def test_the_route_page_carries_the_fixtures_shape(brazos, dana):
    w = _world(brazos, dana)
    fx = _fixture()
    entry = w["page"]["route"]["read_formats"][0]
    assert _keys(entry) == _keys(fx["route_format"])
    assert _keys(entry["read_format"]) == _keys(fx["route_format"]["read_format"])
    assert entry["source"] == fx["route_format"]["source"]
    assert entry["read_format"]["version_id"] == w["version_id"]

    [version] = w["page"]["read_format_versions"]
    assert _keys(version) == _keys(fx["version"])
    assert _keys(version["read_format"]) == _keys(fx["version"]["read_format"])
    assert [q["key"] for q in version["questions"]] == [q["key"] for q in fx["version"]["questions"]]
    for served, mine in zip(version["questions"], fx["version"]["questions"]):
        assert _keys(served) == _keys(mine)
        for field in ("data_type", "options", "is_required", "asked_when", "show_if", "label", "help_text"):
            assert served[field] == mine[field], (served["key"], field)


def test_the_handset_version_door_serves_the_same_shape(brazos, dana):
    w = _world(brazos, dana)
    with tenant_ctx(w["tenant"]):
        one = read_formats.get_version(w["version_id"], published_only=True)
    assert _keys(one) == _keys(_fixture()["version"])


def test_the_phones_reading_item_is_stored_with_no_issue(brazos, dana):
    """The item the phone builds (asserted EQUAL to this file's `reading_item`
    by the handset's own test) goes through the real door: accepted, every
    answer stored, nothing flagged — and the receipt's `answers` block has the
    fixture's keys, which is what the phone reads."""
    w = _world(brazos, dana)
    fx = _fixture()
    item = copy.deepcopy(fx["reading_item"])
    item["route_id"] = str(w["route"].route_id)
    item.pop("premises_id")  # the meter number identifies it on this route
    item["read_format_version_id"] = w["version_id"]
    with tenant_ctx(w["tenant"]):
        out = field_reads.sync_reads(w["reader"], {"items": [item]})
    receipt = out["items"][0]
    assert receipt["result"] == "accepted", receipt
    block = receipt["answers"]
    assert _keys(block) == _keys(fx["receipt_answers"])
    assert block["issues"] == [] and block["needs_review"] is False, block
    assert block["stored"] == fx["receipt_answers"]["stored"]
