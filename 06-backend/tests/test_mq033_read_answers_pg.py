# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 answers' savepoint and the five new tables'
#           RLS, on real PostgreSQL.
# Rules:    BR-MET-1216 (never dropped) · CLAUDE.md hard rule 1 (RLS FORCE) ·
#           **hard-won law 14** — the reason this file exists
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""Law 14 for the answers, proved where it can be: PostgreSQL.

Run::

    DATABASE_URL=postgres://… JOBS_EAGER=false \\
        pytest tests/test_mq033_read_answers_pg.py --ds=config.settings.pgtest

⚠ **THE RED PROOF IS IN THE SUITE** (law 7, in the harness that runs it):
`test_without_the_answers_savepoint_the_request_is_poisoned` turns the nested
`transaction.atomic()` in `field_reads` into a no-op and shows one failed
answer INSERT aborting the whole request — exactly what the savepoint in
`field_reads._record_answers` exists to prevent. On SQLite the same sabotage
passes silently, which is why this file skips there instead of passing.
"""

from __future__ import annotations

import contextlib

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.transaction import TransactionManagementError

from apps.metering import field_reads, read_formats
from apps.metering.field_read_models import FieldRead
from apps.metering.read_format_models import ReadAnswer, ReadFormat

from tests.isolation_helpers import requires_postgres
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor, tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

#: The item whose answers the sabotaged store breaks.
POISON_KEY = "pgq-0002"


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader, history=False)
        fid = read_formats.create_format(dana, {"name": "Walk", "service": "electric"})["id"]
        read_formats.add_question(dana, fid, {"label": "Seal intact?", "data_type": "boolean"})
        read_formats.publish(dana, fid)
        version_id = str(ReadFormat.objects.get(pk=fid).current_version_id)
    return {"tenant": brazos, "reader": reader, "route": route, "version_id": version_id}


def _batch(world):
    w, v = world["route"], world["version_id"]
    items = []
    for key, meter, value in (
        ("pgq-0001", "MTR-0471", "48400"),
        (POISON_KEY, "MTR-0472", "48390"),
        ("pgq-0003", "MTR-0473", "48410"),
    ):
        item = a_reading(key, meter, value, route_id=w.route_id)
        item["read_format_version_id"] = v
        item["answers"] = [{"question_key": "seal_intact", "value": True}]
        items.append(item)
    return {"items": items}


def _poisoning_store(monkeypatch):
    """For ONE item, an answer row that violates `ck_read_answers_issue` — a
    real database refusal, the kind that aborts a PostgreSQL transaction."""
    real = read_formats._store

    def store(rows):
        if rows and rows[0].field_read.key == POISON_KEY:
            ReadAnswer.objects.create(
                tenant_id=rows[0].tenant_id, field_read=rows[0].field_read,
                question_key="x", issue="not-a-lawful-issue",
            )
        return real(rows)

    monkeypatch.setattr(read_formats, "_store", store)


def test_a_failed_answer_insert_loses_nothing_else(world, monkeypatch):
    _poisoning_store(monkeypatch)
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(world["reader"], _batch(world))
        assert [i["result"] for i in out["items"]] == ["accepted"] * 3, out
        poisoned = out["items"][1]["answers"]
        assert poisoned["needs_review"] is True
        assert poisoned["issues"][0]["issue"] == field_reads.HELD_SERVER_ERROR
        # TRUE AFTER the statements ran: all three readings are stored, the
        # poisoned one flagged with none of its answers, the others answered.
        assert FieldRead.objects.filter(key__startswith="pgq-").count() == 3
        assert FieldRead.objects.get(key=POISON_KEY).answers_need_review is True
        assert not ReadAnswer.objects.filter(field_read__key=POISON_KEY).exists()
        assert ReadAnswer.objects.filter(field_read__key__in=["pgq-0001", "pgq-0003"]).count() == 2
        with connection.cursor() as cursor:  # the connection is healthy
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)


def test_without_the_answers_savepoint_the_request_is_poisoned(world, monkeypatch):
    """The sabotage law 7 asks for: the nested atomic() is a no-op, and the
    one failed INSERT aborts every statement after it."""
    _poisoning_store(monkeypatch)

    class _NoSavepoint:
        @staticmethod
        def atomic(*args, **kwargs):
            return contextlib.nullcontext()

    with tenant_ctx(world["tenant"]):
        monkeypatch.setattr(field_reads, "transaction", _NoSavepoint)
        with pytest.raises((DatabaseError, TransactionManagementError)):
            with transaction.atomic():
                field_reads.sync_reads(world["reader"], _batch(world))


def test_rls_is_enabled_and_forced_on_the_five_tables():
    """Read out of `pg_class`, not out of the migration (hard-won law 1)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('read_formats', 'read_format_versions', "
            "'read_format_questions', 'read_format_defaults', 'read_answers') "
            "ORDER BY relname"
        )
        rows = cursor.fetchall()
    assert rows == [
        ("read_answers", True, True),
        ("read_format_defaults", True, True),
        ("read_format_questions", True, True),
        ("read_format_versions", True, True),
        ("read_formats", True, True),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-192-BRC10 (MQ-033 task 10 — read formats server)
# generated: 2026-10-24 by lane MQ033-SERVER
# checklist: A✔ B✔ C✔ D✔ E=deferred(no frontend in this lane) F✔ G✔ H=deferred(no 🔒 path in a test)
# gates: see the lane report
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
