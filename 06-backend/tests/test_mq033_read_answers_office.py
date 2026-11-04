# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 task 13: the office SEES the answers — the
#           Answer filter's vocabulary, the Reads export's answer columns, a
#           photograph answer's bytes.
# Rules:    BR-MET-1218 · BR-SHL-011 (the file is the list the clerk sees) ·
#           NFR-3 · B14 rule 31 · hard rule 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Answers the reader gave, read back by the office.

RED FIRST (hard-won law 7): before this lane every case here failed —
`reads/answer-questions` and `reads/photos/{id}/content` did not exist
(`AttributeError` on `read_formats_api`), and the reads export wrote the
capability row's columns only, so the header assertion read
`'Electric walk · Meter condition' not in [...]`.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest

from apps.metering import read_formats, read_formats_api
from apps.metering.field_read_models import FieldReadPhoto
from apps.tenancy import exports as export_kernel
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.export_helpers import exported_file
from tests.test_be_list_export import wired  # noqa: F401 — fixture
from tests.test_mq033_read_answers import _sync, _with, _world
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import a_reading, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: A 1×1 PNG — the bytes a landed photograph holds.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


@pytest.fixture()
def world(brazos, dana):
    return _world(brazos, dana)


def _answered(world):
    """Two readings that answered, one plain reading with no format."""
    w, v = world["route"], world["version_id"]
    with tenant_ctx(world["tenant"]):
        out = _sync(
            world,
            _with(a_reading("off-0001", "MTR-0471", "48400", route_id=w.route_id), v,
                  [{"question_key": "seal_intact", "value": True},
                   {"question_key": "meter_condition", "value": "Damaged"}]),
            _with(a_reading("off-0002", "MTR-0472", "48390", route_id=w.route_id), v,
                  [{"question_key": "seal_intact", "value": False},
                   {"question_key": "meter_condition", "value": "Good"}]),
        )
    return [item["meter_read_id"] for item in out["items"]]


def _export(world, filters=None):
    with tenant_ctx(world["tenant"]):
        accepted = tenancy_services.request_list_export(
            actor=world["admin"], resource_name="reads", filters=filters or {}
        )
    job = tenancy_models.Job.objects.get(id=accepted["job_id"])
    assert job.status == core_jobs.SUCCEEDED, job.error
    rows = list(csv.reader(io.StringIO(exported_file(job.id).read_text(encoding="utf-8"))))
    return rows[0], rows[1:]


# ══════════════════════════════════════════════════════════════════════════
# The Reads export carries one column per question (task 13, "exported")
# ══════════════════════════════════════════════════════════════════════════
def test_the_reads_export_gains_one_column_per_question_headed_format_and_label(world, wired):  # noqa: F811
    _answered(world)
    header, data = _export(world)
    static = list(export_kernel.export_resource("reads").header)
    assert header[: len(static)] == static
    assert header[len(static):] == [
        "Electric walk · Seal intact?",
        "Electric walk · Photo of the seal",
        "Electric walk · Meter condition",
        "Electric walk · Why not read",
    ]
    by_meter = {dict(zip(header, row))["meter"]: dict(zip(header, row)) for row in data}
    assert by_meter["MTR-0471"]["Electric walk · Seal intact?"] == "true"
    assert by_meter["MTR-0471"]["Electric walk · Meter condition"] == "Damaged"
    assert by_meter["MTR-0472"]["Electric walk · Seal intact?"] == "false"
    assert by_meter["MTR-0472"]["Electric walk · Meter condition"] == "Good"
    # A question nobody answered is an empty cell, never a guessed "no".
    assert by_meter["MTR-0471"]["Electric walk · Why not read"] == ""


def test_the_export_honours_the_lists_answer_filter(world, wired):  # noqa: F811
    _answered(world)
    header, data = _export(world, {"answer[meter_condition]": "Damaged"})
    assert [dict(zip(header, row))["meter"] for row in data] == ["MTR-0471"]


def test_a_file_with_no_answers_is_exactly_the_capability_row(world, wired):  # noqa: F811
    """No reading carried a format — the file is byte-for-byte the columns it
    always had (no empty answer columns)."""
    header, _data = _export(world)
    assert header == list(export_kernel.export_resource("reads").header)


# ══════════════════════════════════════════════════════════════════════════
# The Answer filter's vocabulary — published questions, any office role
# ══════════════════════════════════════════════════════════════════════════
def _questions(world, role="billing_clerk", **query):
    return api_call(
        read_formats_api.answer_questions, "get",
        user=world["admin"].user, role=role, tenant=world["tenant"], query=query,
    )


def test_the_vocabulary_lists_published_questions_to_a_clerk_paged(world):
    with tenant_ctx(world["tenant"]):
        # A DRAFT format is not offered — nothing could have answered it.
        draft = read_formats.create_format(world["admin"], {"name": "Water walk", "service": "water"})
        read_formats.add_question(world["admin"], draft["id"], {"label": "Dog on site?", "data_type": "boolean"})
    response = _questions(world)
    assert response.status_code == 200, response.data
    body = response.data
    assert body["count"] == 3 and "results" in body  # the photo question is not offered
    first = body["results"][0]
    assert (first["format_name"], first["version_no"], first["key"], first["label"], first["data_type"]) == (
        "Electric walk", 1, "seal_intact", "Seal intact?", "boolean",
    )
    condition = next(r for r in body["results"] if r["key"] == "meter_condition")
    assert condition["options"] == ["Good", "Damaged", "Missing"]
    assert "Dog on site?" not in [r["label"] for r in body["results"]]


def test_the_vocabulary_searches_label_or_format_and_names_keys(world):
    by_label = _questions(world, q="condition").data["results"]
    assert [r["key"] for r in by_label] == ["meter_condition"]
    by_format = _questions(world, q="electric").data["count"]
    assert by_format == 3
    by_key = _questions(world, key="seal_intact").data["results"]
    assert [r["label"] for r in by_key] == ["Seal intact?"]


# ══════════════════════════════════════════════════════════════════════════
# A photograph answer's bytes — same-origin, this tenant only
# ══════════════════════════════════════════════════════════════════════════
def test_a_landed_photo_is_served_and_an_unknown_one_is_a_404(world):
    photo_id = uuid.uuid4()
    with tenant_ctx(world["tenant"]):
        FieldReadPhoto.objects.create(
            tenant=world["tenant"], photo_id=photo_id, sha256="0" * 64, key="off-photo",
            state=FieldReadPhoto.STATE_LANDED, content_type="image/png", data=PNG,
            bytes_received=len(PNG),
        )
    ok = api_call(
        read_formats_api.answer_photo_content, "get",
        user=world["admin"].user, role="billing_clerk", tenant=world["tenant"],
        photo_id=str(photo_id),
    )
    assert ok.status_code == 200
    assert ok["Content-Type"] == "image/png" and ok.content == PNG
    assert ok["X-Content-Type-Options"] == "nosniff"
    missing = api_call(
        read_formats_api.answer_photo_content, "get",
        user=world["admin"].user, role="billing_clerk", tenant=world["tenant"],
        photo_id=str(uuid.uuid4()),
    )
    assert missing.status_code == 404
