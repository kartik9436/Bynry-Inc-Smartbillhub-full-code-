# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 answers on each route reading: stored,
#           stamped with the version, checked, flagged, never dropped; a job
#           raised for a matching answer; shown on the reading and filterable.
# Rules:    BR-MET-1214 · BR-MET-1215 · BR-MET-1216 · BR-MET-1217 ·
#           BR-MET-1218 · BR-WRK-067 · hard rule 6
# Tests:    this file (SQLite) · test_mq033_read_answers_pg.py (law 14)
# ───────────────────────────────────────────────────────
"""The reads door with a format: every answer kept, a bad one flagged.

RED FIRST (hard-won law 7): at `baf29dbca` every case here fails on
`ImportError` (no `read_formats`); with the module present and the
`field_reads._record_answers` call removed, every case asserting a stored
answer fails — the item's `answers` were ignored before this lane.

PO, verbatim (decision log 2026-10-24, *"SUMMARY CONFIRMED"*): answers
*"never cause a reading to be dropped (stored and flagged instead)"*.
"""

from __future__ import annotations

import uuid

import pytest

from apps.metering import field_reads, read_formats, selectors
from apps.metering import models as metering_models
from apps.metering.field_read_models import FieldRead
from apps.metering.read_format_models import ReadAnswer, ReadFormat
from apps.work import connection_models as work_tables
from apps.work.route_finding_models import WorkRouteFinding

from tests.test_cr187_order_helpers import template
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import (
    a_cant_read,
    a_reading,
    build_route,
    reader_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _publish_walk(admin, tenant, *, raise_template=None, extra=()):
    fid = read_formats.create_format(admin, {"name": "Electric walk", "service": "electric"})["id"]
    questions = [
        {"label": "Seal intact?", "data_type": "boolean", "is_required": True},
        {"label": "Photo of the seal", "data_type": "photo", "is_required": True,
         "show_if": {"question_key": "seal_intact", "answer": False}},
        {"label": "Meter condition", "data_type": "select",
         "options": ["Good", "Damaged", "Missing"],
         **({"raise_work": {"on_answer": "Damaged", "template_id": str(raise_template)}}
            if raise_template else {})},
        {"label": "Why not read", "data_type": "text", "is_required": True,
         "asked_when": "cant_read"},
        *extra,
    ]
    for q in questions:
        read_formats.add_question(admin, fid, q)
    read_formats.publish(admin, fid)
    return fid


def _world(brazos, dana, *, history=False, raise_template=False, extra=()):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader, history=history)
        tid = template(dana, brazos, "Meter repair") if raise_template else None
        fid = _publish_walk(dana, brazos, raise_template=tid, extra=extra)
        read_formats.set_cycle_format(dana, route.cycle_id, {"read_format_id": fid})
        version_id = str(ReadFormat.objects.get(pk=fid).current_version_id)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route,
            "format_id": fid, "version_id": version_id, "template_id": tid}


@pytest.fixture()
def world(brazos, dana):
    return _world(brazos, dana)


def _with(item, version_id, answers):
    item["read_format_version_id"] = version_id
    item["answers"] = answers
    return item


def _sync(world, *items):
    return field_reads.sync_reads(world["reader"], {"items": list(items)})


def _answers(key):
    return {
        a.question_key: a for a in ReadAnswer.objects.filter(field_read__key=key)
    }


# ══════════════════════════════════════════════════════════════════════════
# Stored with the reading, stamped with the version (BR-MET-1215)
# ══════════════════════════════════════════════════════════════════════════
def test_lawful_answers_are_stored_stamped_and_the_reading_posts(world):
    w, v = world["route"], world["version_id"]
    with tenant_ctx(world["tenant"]):
        item = _with(
            a_reading("ans-0001", "MTR-0471", "48400", route_id=w.route_id),
            v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "meter_condition", "value": "Good"}],
        )
        receipt = _sync(world, item)["items"][0]
        assert receipt["result"] == "accepted" and receipt["outcome"] == "posted", receipt
        assert receipt["answers"] == {
            "version_id": v, "stored": 2, "needs_review": False, "issues": [], "work": [],
        }
        row = FieldRead.objects.get(key="ans-0001")
        assert str(row.read_format_version_id) == v and row.answers_need_review is False
        stored = _answers("ans-0001")
        assert stored["seal_intact"].value is True and stored["seal_intact"].value_text == "true"
        assert stored["meter_condition"].value == "Good"
        assert all(str(a.version_id) == v for a in stored.values())


def test_bad_answers_never_drop_the_reading_they_are_stored_and_flagged(world):
    """Wrong type, not an option, an unknown question and a missing required
    answer: the reading POSTS exactly as it would have, every answer is a row."""
    w, v = world["route"], world["version_id"]
    with tenant_ctx(world["tenant"]):
        item = _with(
            a_reading("ans-0002", "MTR-0472", "48390", route_id=w.route_id),
            v,
            [{"question_key": "meter_condition", "value": "Purple"},
             {"question_key": "dog_on_site", "value": "yes"}],
        )
        receipt = _sync(world, item)["items"][0]
        assert receipt["result"] == "accepted" and receipt["outcome"] == "posted", receipt
        assert metering_models.MeterRead.objects.filter(id=receipt["meter_read_id"]).exists()
        block = receipt["answers"]
        assert block["needs_review"] is True
        assert sorted((i["question_key"], i["issue"]) for i in block["issues"]) == [
            ("dog_on_site", "unknown_question"),
            ("meter_condition", "not_an_option"),
            ("seal_intact", "required_missing"),
        ]
        stored = _answers("ans-0002")
        assert stored["meter_condition"].value == "Purple"  # kept AS SENT
        assert stored["dog_on_site"].value == "yes"
        assert stored["seal_intact"].value is None
        assert FieldRead.objects.get(key="ans-0002").answers_need_review is True


def test_a_follow_up_is_required_only_when_shown_and_flagged_when_not(world):
    w, v = world["route"], world["version_id"]
    photo = str(uuid.uuid4())
    with tenant_ctx(world["tenant"]):
        broken_no_photo = _with(
            a_reading("ans-0003", "MTR-0471", "48400", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": False}],
        )
        intact_with_photo = _with(
            a_reading("ans-0004", "MTR-0473", "48410", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "photo_of_the_seal", "photo_id": photo}],
        )
        broken_with_photo = _with(
            a_reading("ans-0005", "MTR-0474", "48420", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": "false"},
             {"question_key": "photo_of_the_seal", "photo_id": photo}],
        )
        out = _sync(world, broken_no_photo, intact_with_photo, broken_with_photo)
        issues = [r["answers"]["issues"] for r in out["items"]]
        assert issues[0] == [{"question_key": "photo_of_the_seal", "issue": "required_missing"}]
        assert issues[1] == [{"question_key": "photo_of_the_seal", "issue": "not_shown"}]
        assert issues[2] == []
        assert str(_answers("ans-0005")["photo_of_the_seal"].photo_id) == photo
        assert all(r["result"] == "accepted" for r in out["items"])


def test_cant_read_questions_are_asked_of_a_cant_read_and_not_of_a_figure(world):
    w, v = world["route"], world["version_id"]
    with tenant_ctx(world["tenant"]):
        cant = _with(
            a_cant_read("ans-0006", "MTR-0471", "dog", route_id=w.route_id), v,
            [{"question_key": "why_not_read", "value": "Loose dog in the yard"}],
        )
        figure = _with(
            a_reading("ans-0007", "MTR-0472", "48390", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "why_not_read", "value": "n/a"}],
        )
        out = _sync(world, cant, figure)
        assert out["items"][0]["outcome"] == "recorded"
        assert out["items"][0]["answers"]["issues"] == []
        assert out["items"][1]["answers"]["issues"] == [
            {"question_key": "why_not_read", "issue": "not_asked"}
        ]


def test_an_unknown_version_keeps_the_answers_flagged(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        item = _with(
            a_reading("ans-0008", "MTR-0471", "48400", route_id=w.route_id),
            str(uuid.uuid4()),
            [{"question_key": "seal_intact", "value": True}],
        )
        receipt = _sync(world, item)["items"][0]
        assert receipt["result"] == "accepted"
        assert receipt["answers"]["version_id"] is None
        assert receipt["answers"]["issues"] == [
            {"question_key": "seal_intact", "issue": "version_unknown"}
        ]
        assert _answers("ans-0008")["seal_intact"].version_id is None


def test_a_reading_with_no_format_is_exactly_as_before(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        receipt = _sync(world, a_reading("ans-0009", "MTR-0471", "48400", route_id=w.route_id))[
            "items"
        ][0]
        assert receipt["result"] == "accepted" and "answers" not in receipt
        assert not ReadAnswer.objects.filter(field_read__key="ans-0009").exists()


def test_once_per_stop_is_satisfied_by_any_reading_at_the_stop(brazos, dana):
    """1318 Maple holds MTR-0471 and MTR-0472: the gate code asked once."""
    world = _world(
        brazos, dana,
        extra=({"label": "Gate code", "data_type": "text", "is_required": True,
                "asked_when": "once_per_stop"},),
    )
    w, v = world["route"], world["version_id"]
    stop = w.premises[0]
    with tenant_ctx(brazos):
        first = _with(
            a_reading("ans-0010", "MTR-0471", "48400", route_id=w.route_id, premises_id=stop), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "gate_code", "value": "4471"}],
        )
        second = _with(
            a_reading("ans-0011", "MTR-0472", "48390", route_id=w.route_id, premises_id=stop), v,
            [{"question_key": "seal_intact", "value": True}],
        )
        lone = _with(
            a_reading("ans-0012", "MTR-0473", "48410", route_id=w.route_id,
                      premises_id=w.premises[1]), v,
            [{"question_key": "seal_intact", "value": True}],
        )
        out = _sync(world, first, second, lone)
        assert out["items"][0]["answers"]["issues"] == []
        assert out["items"][1]["answers"]["issues"] == []
        assert out["items"][2]["answers"]["issues"] == [
            {"question_key": "gate_code", "issue": "required_missing"}
        ]


def test_out_of_range_questions_follow_the_engines_verdict(brazos, dana):
    """71,400 against a last dial of 47,700 is flagged HIGH by the engine
    (`test_cr187_reads_sync.test_out_of_range_is_accepted_and_flagged`): the
    out-of-range question is asked of it, and not of an ordinary reading."""
    world = _world(
        brazos, dana, history=True,
        extra=({"label": "Reason for high read", "data_type": "text", "is_required": True,
                "asked_when": "out_of_range"},),
    )
    w, v = world["route"], world["version_id"]
    with tenant_ctx(brazos):
        high = _with(
            a_reading("ans-0013", "MTR-0471", "71400", route_id=w.route_id, accepted_anyway=True), v,
            [{"question_key": "seal_intact", "value": True}],
        )
        normal = _with(
            a_reading("ans-0014", "MTR-0472", "48400", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "reason_for_high_read", "value": "pool pump"}],
        )
        out = _sync(world, high, normal)
        assert out["items"][0]["answers"]["issues"] == [
            {"question_key": "reason_for_high_read", "issue": "required_missing"}
        ], out["items"][0]
        assert out["items"][1]["answers"]["issues"] == [
            {"question_key": "reason_for_high_read", "issue": "not_asked"}
        ], out["items"][1].get("engine")


# ══════════════════════════════════════════════════════════════════════════
# Raise a work order (BR-MET-1217)
# ══════════════════════════════════════════════════════════════════════════
def test_a_matching_answer_raises_one_job_linked_back_and_a_resend_raises_none(brazos, dana):
    world = _world(brazos, dana, raise_template=True)
    w, v = world["route"], world["version_id"]
    with tenant_ctx(brazos):
        item = _with(
            a_reading("ans-0020", "MTR-0471", "48400", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "meter_condition", "value": "Damaged"}],
        )
        receipt = _sync(world, item)["items"][0]
        (raised,) = receipt["answers"]["work"]
        assert raised["question_key"] == "meter_condition"
        assert raised["finding_status"] == "work_order_created", raised
        order_no = raised["work_order"]["order_no"]
        assert order_no.startswith("WO-")

        finding = WorkRouteFinding.objects.get(key="read-answer:ans-0020:meter_condition")
        assert finding.kind == "read_answer" and finding.conversion == "by_read_format"
        assert finding.detail["meter_read_id"] == receipt["meter_read_id"]
        assert finding.detail["answer"] == "Damaged"
        order = work_tables.WorkOrder.objects.get(pk=finding.work_order_id)
        assert str(order.template_id) == str(world["template_id"])
        assert str(order.asset_id) == w.meters["MTR-0471"]["id"]
        answer = _answers("ans-0020")["meter_condition"]
        assert answer.work_order_no == order_no

        # Hard rule 6 — the same item again is a duplicate; no second job.
        again = _sync(world, item)["items"][0]
        assert again["result"] == "duplicate"
        assert WorkRouteFinding.objects.filter(kind="read_answer").count() == 1
        # A different reading answering the same way at another meter raises
        # its own job (idempotent on reading + question, not on the answer).
        other = _with(
            a_reading("ans-0021", "MTR-0472", "48390", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "meter_condition", "value": "Damaged"}],
        )
        _sync(world, other)
        assert WorkRouteFinding.objects.filter(kind="read_answer").count() == 2


def test_a_non_matching_or_flagged_answer_raises_nothing(brazos, dana):
    world = _world(brazos, dana, raise_template=True)
    w, v = world["route"], world["version_id"]
    with tenant_ctx(brazos):
        good = _with(
            a_reading("ans-0022", "MTR-0471", "48400", route_id=w.route_id), v,
            [{"question_key": "seal_intact", "value": True},
             {"question_key": "meter_condition", "value": "Good"}],
        )
        assert _sync(world, good)["items"][0]["answers"]["work"] == []
        assert not WorkRouteFinding.objects.filter(kind="read_answer").exists()


# ══════════════════════════════════════════════════════════════════════════
# Shown on the reading; filterable in the Reads list (BR-MET-1218)
# ══════════════════════════════════════════════════════════════════════════
def test_answers_show_on_the_reading_and_filter_the_reads_list(world):
    w, v = world["route"], world["version_id"]
    with tenant_ctx(world["tenant"]):
        out = _sync(
            world,
            _with(a_reading("ans-0030", "MTR-0471", "48400", route_id=w.route_id), v,
                  [{"question_key": "seal_intact", "value": True},
                   {"question_key": "meter_condition", "value": "Damaged"}]),
            _with(a_reading("ans-0031", "MTR-0472", "48390", route_id=w.route_id), v,
                  [{"question_key": "seal_intact", "value": True},
                   {"question_key": "meter_condition", "value": "Good"}]),
        )
        damaged_read, good_read = (r["meter_read_id"] for r in out["items"])
        detail = read_formats.answers_for_meter_read(damaged_read)
        assert detail["read_format"]["version_no"] == 1
        assert detail["needs_review"] is False
        assert [(a["question_key"], a["label"], a["value"]) for a in detail["answers"]] == [
            ("seal_intact", "Seal intact?", True),
            ("meter_condition", "Meter condition", "Damaged"),
        ]
        ids = {
            str(r.id)
            for r in selectors.read_result_set(answer_filters={"meter_condition": "Damaged"})
        }
        assert ids == {damaged_read}
        both = {
            str(r.id) for r in selectors.read_result_set(answer_filters={"seal_intact": "true"})
        }
        assert both == {damaged_read, good_read}
        assert read_formats.answer_filters(
            {"answer[meter_condition]": "Good", "f.status": "ok", "answer[]": "x"}
        ) == {"meter_condition": "Good"}
