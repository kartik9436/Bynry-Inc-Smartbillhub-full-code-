# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10601 — the job sync door refused the phone's Unable-to-read
#           reading (and nothing proved its text reading) because
#           `evidence.set_reading` knew only a number with a unit
# Rules:    TECHNICIAN SYNC DESIGN (decision log 2026-10-04: no field record is
#           ever dropped) · BR-WRK-039 (flag, never refuse) · hard rule 3 (a
#           figure carries its unit; no figure carries no consumption) · hard
#           rule 7 (audited) · HR-1 (404)
# Tests:    this file · test_def_wrk_10601_job_reading_shapes_pg.py (PostgreSQL)
#           · field-app/tests/sync/jobReadingShapes.test.ts (the handset)
# ───────────────────────────────────────────────────────
"""The three reading shapes the phone sends, through the real sync door.

`field-app/tests/sync/support/jobReadingShapes.json` holds the phone's exact
payloads. `field-app/tests/sync/jobReadingShapes.test.ts` asserts the phone's
own `recordReading` / `recordTextReading` still produce exactly those, and this
file POSTs exactly those to `POST /work/mobile/jobs/{id}/sync`. Neither side can
move without the other going red — which is the gap DEF-WRK-10601 fell through:
the phone's tests ran against a fake server that accepted everything, and the
server's tests only ever sent numbers through this door."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.work import api, evidence
from apps.work import models as work_models
from apps.work import checklist

from tests.test_cr187_gaps import _call, _token
from tests.test_cr187_order_helpers import job
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · audit_rows
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SHAPES_FILE = (
    Path(__file__).resolve().parents[2]
    / "field-app" / "tests" / "sync" / "support" / "jobReadingShapes.json"
)
SHAPES = json.loads(SHAPES_FILE.read_text(encoding="utf-8"))


def _shape(name: str, reading_id, unit: str) -> dict:
    """The phone's payload, with only its two placeholders filled in."""
    out = {}
    for k, v in SHAPES[name].items():
        if v == "{reading_id}":
            v = str(reading_id)
        elif v == "{unit}":
            v = unit
        out[k] = v
    return out


def _readings(oid):
    return list(work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq"))


def _send(tenant, tech, oid, payloads, prefix="shape"):
    """POST the payloads to the job's sync door as the technician's phone does:
    every item stamped with its captor's token, in capture order."""
    token = _token(tech)
    items = [
        {"key": f"{prefix}-{n}", "kind": "reading", "seq": n, "capture_token": token,
         "captured_at": "2026-03-15T16:07:00Z", "payload": p}
        for n, p in enumerate(payloads, start=1)
    ]
    answer = _call(api.mobile_sync, tenant, tech, {"items": items}, order_id=oid)
    assert answer.status_code == 200, answer.data
    # A refusal names its reason in the failure, not just a count.
    return {**answer.data, "refusals": [
        i.get("detail") for i in answer.data["items"] if i["result"] != "accepted"
    ]}


def _as_text(row):
    work_models.WorkOrderReading.objects.filter(pk=row.id).update(kind="text", unit_of_measure="")
    row.refresh_from_db()
    return row


def test_the_shape_file_holds_the_three_shapes_and_nothing_else():
    assert set(SHAPES) == {"number", "text", "unable"}


def test_a_number_reading_is_accepted_and_stored_with_its_unit(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _readings(oid)[0]
        out = _send(brazos, tech, oid, [_shape("number", row.id, row.unit_of_measure)])
        row.refresh_from_db()
    assert out["accepted"] == 1 and out["refused"] == 0, out["refusals"]
    assert str(row.value) == "1204.0000"
    assert row.unable_to_read is False


def test_a_text_reading_is_accepted_and_stored_as_typed(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _as_text(_readings(oid)[2])
        out = _send(brazos, tech, oid, [_shape("text", row.id, "")])
        row.refresh_from_db()
        ready = evidence.close_readiness(oid)
    assert out["accepted"] == 1 and out["refused"] == 0, out["refusals"]
    assert row.value_text == "W-5000-N"
    assert row.value is None
    # DEF-WRK-10602 — the words ANSWER the reading, as the phone counts them.
    assert ready["readings_captured"] == 1


def test_unable_to_read_is_accepted_with_no_figure_and_flagged_for_the_office(brazos, dana, audit_rows):
    """The case that was refused `work.reading.value_not_a_number` and stuck."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _readings(oid)[0]
        out = _send(brazos, tech, oid, [_shape("unable", row.id, row.unit_of_measure)])
        row.refresh_from_db()
        ready = evidence.close_readiness(oid)
        page = checklist.checklist(oid)
    assert out["accepted"] == 1 and out["refused"] == 0, out["refusals"]
    assert row.unable_to_read is True
    assert row.value is None and row.value_text is None and row.in_range is None
    # DEF-MET-10609 — the phone sends one reason CODE from the shared can't-read
    # list and an optional note; the office reads the reason's NAME.
    assert row.unable_reason == "dog" and row.unable_note == "Dog at the gate"
    assert row.captured_at is not None
    assert {"kind": "unable_to_read", "scope": "reading", "id": str(row.id),
            "prompt": row.prompt, "reason": "Dog"} in ready["flagged"]
    assert ready["readings_captured"] == 1
    served = next(r for r in page["readings"] if r["id"] == str(row.id))
    assert served["unable_to_read"] is True and served["unable_reason"] == "dog"
    assert served["unable_reason_name"] == "Dog" and served["unable_note"] == "Dog at the gate"
    captured = [r for r in audit_rows if r.get("action") == "work.reading.captured"]
    assert len(captured) == 1
    assert captured[0]["after"]["unable_to_read"] is True


def test_unable_to_read_on_a_text_reading_is_accepted_too(brazos, dana):
    """The phone marks a TEXT reading unable with `unit: ""` — no unit to check."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _as_text(_readings(oid)[2])
        out = _send(brazos, tech, oid, [_shape("unable", row.id, "")])
        row.refresh_from_db()
    assert out["accepted"] == 1, out["refusals"]
    assert row.unable_to_read is True and row.value_text is None


def test_a_reason_sent_with_unable_is_kept(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _readings(oid)[0]
        body = {**_shape("unable", row.id, row.unit_of_measure), "unable_reason": "Meter buried"}
        out = _send(brazos, tech, oid, [body])
        row.refresh_from_db()
    assert out["accepted"] == 1, out["refusals"]
    assert row.unable_reason == "Meter buried"


def test_a_figure_after_unable_clears_the_flag(brazos, dana):
    """The technician digs the meter out and reads it: the figure is the answer."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _readings(oid)[0]
        out = _send(brazos, tech, oid, [
            {**_shape("unable", row.id, row.unit_of_measure), "unable_reason": "Meter buried"},
            _shape("number", row.id, row.unit_of_measure),
        ])
        row.refresh_from_db()
        ready = evidence.close_readiness(oid)
    assert out["accepted"] == 2, out["refusals"]
    assert row.unable_to_read is False and row.unable_reason is None
    assert str(row.value) == "1204.0000"
    assert not [f for f in ready["flagged"] if f["kind"] == "unable_to_read"]


def test_an_unable_reading_posts_no_meter_read(brazos, dana):
    """No figure, no consumption: the posting path skips it (hard rule 3)."""
    from apps.work.seams import metering_seam

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        row = _readings(oid)[0]
        assert row.posts_as_meter_read
        _send(brazos, tech, oid, [_shape("unable", row.id, row.unit_of_measure)])
        answer = metering_seam.post_set_reads(dana, oid)
    assert answer["posted_reads"] == 0
    assert answer["skipped"][0]["reason"] == "no_value_captured"
