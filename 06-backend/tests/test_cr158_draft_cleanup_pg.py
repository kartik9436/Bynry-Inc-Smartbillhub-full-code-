# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — its "not done" item, ruled 2026-10-02 (option A).
# Rules:    PO ruling 2026-10-02, verbatim: "A · Delete it 30 days after her
#           last visit. Her draft and the photo are deleted on 31 October, and
#           the deletion is logged. If she returns on 20 October, the 30 days
#           start again." · CLAUDE.md hard rules 1 and 7 · hard-won law 14
#           (a DELETE inside per-draft savepoints is proved on PostgreSQL)
# Tests:    this file
# Impacts:  apps/portal/draft_cleanup.py · apps/portal/applications.py
#           (last_visited_at) · apps/portal/migrations/0012
# ───────────────────────────────────────────────────────
"""The nightly clean-up of unsent portal applications, on PostgreSQL, with a
frozen clock.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://<user>@127.0.0.1:55433/<db> \\
        pytest tests/test_cr158_draft_cleanup_pg.py

⚠ **THE CLOCK.** `django.utils.timezone.now` is replaced for the length of each
case, so the applicant's visits (`auto_now`, the `last_visited_at` stamp) and
the job's *today* are all read from one controllable instant. The dates are the
PO's own — 1 October, 20 October, 31 October — in 2025, so that nothing written
lies in the database's future.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
  * *"the draft is gone"* passes if the job deletes EVERYTHING — so every
    deleting case keeps a draft that must survive beside it;
  * *"the survivor survives"* passes if the job deletes NOTHING — so every
    surviving case is followed by a later run that does delete it;
  * *"the files are gone"* passes over files that were never uploaded — so the
    upload is counted before the run.

Every case carries `requires_postgres` and SKIPS on SQLite rather than passing
vacuously.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone

import pytest
from django.db import connection
from django.utils import timezone

from apps.customers import models as customers_models
from apps.portal import draft_cleanup, guest_api, models
from apps.tenancy.document_models import StoredDocument
from core.tenancy import tenant_context
from tests.isolation_helpers import requires_postgres
from tests.test_cr158_portal_application_documents import (  # noqa: F401
    COMPLETE,
    PDF,
    PNG,
    _send,
    _upload,
    docs_dir,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

MARIA = "d7a1e2f3-0001-4a7b-8c9d-0e1f2a3b4c5d"
KEPT = "d7a1e2f3-0002-4a7b-8c9d-0e1f2a3b4c5d"


def at(text: str) -> datetime:
    """An instant in UTC. Noon keeps the calendar day the same in every North
    American zone and in UTC, so the case does not depend on the utility's."""
    return datetime.fromisoformat(text).replace(tzinfo=dt_timezone.utc)


class Clock:
    def __init__(self, monkeypatch):
        self.now = at("2025-10-01T12:00:00")
        monkeypatch.setattr(timezone, "now", lambda: self.now)

    def set(self, text: str) -> None:
        self.now = at(text)


@pytest.fixture()
def clock(monkeypatch):
    return Clock(monkeypatch)


@pytest.fixture()
def portal_on(pine_hill, sarah, docs_dir):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


def _save(tenant, token):
    response = api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data={**COMPLETE, "requested_start": "2099-01-15"},
        token=token,
    )
    assert response.status_code == 200, response.data
    return response


def _open(tenant, token):
    return api_call(
        guest_api.application_draft,
        "get",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        token=token,
    )


def _run(tenant):
    return draft_cleanup.cleanup_one(tenant.subdomain)


def _drafts(tenant) -> set[str]:
    with tenant_context(tenant.id):
        # The tenant predicate is written out: this suite may run as a role
        # that bypasses RLS, and then the context alone would show every
        # utility's drafts and the cross-utility case would read nonsense.
        return set(
            models.PortalApplicationDraft.objects.filter(tenant_id=tenant.id).values_list(
                "token", flat=True
            )
        )


def _held(tenant) -> tuple[int, int]:
    """(rows, stored bytes) of held files — read in SQL, so the bytes are
    counted by the database and not by a Python object that might be cached."""
    with tenant_context(tenant.id), connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*), coalesce(sum(octet_length(payload)), 0) "
            "FROM portal_application_documents WHERE tenant_id = %s",
            [str(tenant.id)],
        )
        rows, size = cursor.fetchone()
    return int(rows), int(size)


def _deletions(audit_rows) -> list[dict]:
    return [r for r in audit_rows if r["action"] == draft_cleanup.AUDIT_ACTION]


# ── 1 · 31 days: the draft, its two files and their bytes go; one audit row ──


@requires_postgres
@pytest.mark.django_db(transaction=False)
def test_a_draft_last_visited_31_days_ago_goes_with_its_two_files_and_one_audit_row(
    portal_on, clock, audit_rows
):
    clock.set("2025-09-30T12:00:00")  # 31 days before 31 October
    _save(portal_on, MARIA)
    assert _upload(portal_on, PDF, "tenancy-agreement.pdf", token=MARIA).status_code == 200
    assert _upload(portal_on, PNG, "photo-id.png", token=MARIA).status_code == 200
    clock.set("2025-10-20T12:00:00")
    _save(portal_on, KEPT)  # the survivor beside it — the job is not "delete all"
    assert _held(portal_on) == (2, len(PDF) + len(PNG))

    clock.set("2025-10-31T12:00:00")
    result = _run(portal_on)

    assert result["drafts"] == 1 and result["files"] == 2, result
    assert _drafts(portal_on) == {KEPT}
    assert _held(portal_on) == (0, 0)  # the rows AND the bytes
    rows = _deletions(audit_rows)
    assert len(rows) == 1
    row = rows[0]
    assert row["entity_type"] == "portal_application_draft"
    assert row["before"]["files_deleted"] == 2
    assert row["before"]["reason"] == "unsent 30 days"
    assert row["before"]["last_visited_at"].startswith("2025-09-30")
    # Never a file's name or contents, never the applicant, never the link.
    written = json.dumps(row, default=str)
    for secret in (
        "tenancy-agreement",
        "photo-id",
        "Daniel",
        "Okafor",
        "d.okafor@example.test",
        "555-7730",
        MARIA,
        "Palm Ct",
    ):
        assert secret not in written, secret


# ── 2 · 29 days: survives — and goes the day it turns 30 ─────────────────────


@requires_postgres
@pytest.mark.django_db
def test_a_draft_last_visited_29_days_ago_survives(portal_on, clock, audit_rows):
    clock.set("2025-10-02T12:00:00")  # 29 days before 31 October
    _save(portal_on, MARIA)
    assert _upload(portal_on, PDF, "tenancy-agreement.pdf", token=MARIA).status_code == 200

    clock.set("2025-10-31T12:00:00")
    assert _run(portal_on)["drafts"] == 0
    assert _drafts(portal_on) == {MARIA}
    assert _held(portal_on)[0] == 1
    assert _deletions(audit_rows) == []

    clock.set("2025-11-01T12:00:00")  # 30 days — now it goes
    assert _run(portal_on) == {"subdomain": portal_on.subdomain, "swept": True, "drafts": 1, "files": 1}
    assert _drafts(portal_on) == set()


# ── 3 · the PO's worked figure, and a return on 20 October restarts it ──────


@requires_postgres
@pytest.mark.django_db
def test_the_rulings_own_figure_1_october_goes_on_31_october_not_on_30(
    portal_on, clock
):
    """Maria, 1 October, a photo of her licence, never returns: deleted on
    31 October — the date the PO was shown — and not a day before."""
    clock.set("2025-10-01T12:00:00")
    _save(portal_on, MARIA)
    assert _upload(portal_on, PNG, "licence.png", token=MARIA).status_code == 200

    clock.set("2025-10-30T12:00:00")
    assert _run(portal_on)["drafts"] == 0
    clock.set("2025-10-31T12:00:00")
    assert _run(portal_on)["drafts"] == 1
    assert _held(portal_on) == (0, 0)


@requires_postgres
@pytest.mark.django_db
def test_a_return_on_20_october_restarts_the_30_days(portal_on, clock):
    """She OPENS her link on 20 October and changes nothing. That is a visit:
    the draft survives 31 October and goes on 19 November, 30 days after it."""
    clock.set("2025-10-01T12:00:00")
    _save(portal_on, MARIA)
    assert _upload(portal_on, PNG, "licence.png", token=MARIA).status_code == 200

    clock.set("2025-10-20T12:00:00")
    assert _open(portal_on, MARIA).status_code == 200  # a read — no save
    with tenant_context(portal_on.id):
        row = models.PortalApplicationDraft.objects.get(token=MARIA)
        assert row.last_visited_at == at("2025-10-20T12:00:00")
        assert row.updated_at == at("2025-10-01T12:00:00")  # nothing changed

    clock.set("2025-10-31T12:00:00")
    assert _run(portal_on)["drafts"] == 0
    clock.set("2025-11-18T12:00:00")
    assert _run(portal_on)["drafts"] == 0
    assert _drafts(portal_on) == {MARIA}
    clock.set("2025-11-19T12:00:00")
    assert _run(portal_on)["drafts"] == 1
    assert _drafts(portal_on) == set()


@requires_postgres
@pytest.mark.django_db
def test_a_draft_from_before_the_column_counts_from_its_last_save(portal_on, clock):
    """`last_visited_at` is NULL on a draft written before `portal/0012`; its
    last save (`updated_at`) is then the last visit anybody can prove."""
    clock.set("2025-10-01T12:00:00")
    _save(portal_on, MARIA)
    with tenant_context(portal_on.id):
        models.PortalApplicationDraft.objects.filter(token=MARIA).update(last_visited_at=None)
    clock.set("2025-10-30T12:00:00")
    assert _run(portal_on)["drafts"] == 0
    clock.set("2025-10-31T12:00:00")
    assert _run(portal_on)["drafts"] == 1


# ── 4 · a SENT application's documents are never touched ─────────────────────


@requires_postgres
@pytest.mark.django_db
def test_a_sent_applications_documents_are_untouched(portal_on, clock, audit_rows):
    clock.set("2025-09-01T12:00:00")
    _save(portal_on, MARIA)
    assert _upload(portal_on, PDF, "tenancy-agreement.pdf", token=MARIA).status_code == 200
    assert _upload(portal_on, PNG, "photo-id.png", token=MARIA).status_code == 200
    sent = _send(portal_on, token=MARIA)
    assert sent.status_code in (200, 201), sent.data
    request_id = sent.data["request_id"]
    with tenant_context(portal_on.id):
        filed = list(
            customers_models.ServiceRequestDocument.objects.filter(request_id=request_id)
            .order_by("id")
            .values_list("id", flat=True)
        )
        stored = StoredDocument.objects.count()
    assert len(filed) == 2 and stored >= 2

    clock.set("2025-12-31T12:00:00")  # four months later
    assert _run(portal_on)["drafts"] == 0
    with tenant_context(portal_on.id):
        assert list(
            customers_models.ServiceRequestDocument.objects.filter(request_id=request_id)
            .order_by("id")
            .values_list("id", flat=True)
        ) == filed
        assert StoredDocument.objects.count() == stored
        # The sent draft row is the record of what was submitted; it stays.
        assert models.PortalApplicationDraft.objects.filter(
            token=MARIA, submitted_at__isnull=False
        ).exists()
    assert _deletions(audit_rows) == []


# ── 5 · another utility's drafts are untouched by this utility's run ─────────


@requires_postgres
@pytest.mark.django_db
def test_another_utilitys_drafts_are_untouched_by_this_utilitys_run(
    portal_on, oak_ridge, elena, clock
):
    switch_on(oak_ridge, elena)
    clock.set("2025-09-01T12:00:00")
    _save(portal_on, MARIA)
    _save(oak_ridge, KEPT)
    assert _upload(oak_ridge, PDF, "tenancy-agreement.pdf", token=KEPT).status_code == 200

    clock.set("2025-12-31T12:00:00")
    assert _run(portal_on)["drafts"] == 1
    assert _drafts(portal_on) == set()
    assert _drafts(oak_ridge) == {KEPT}
    assert _held(oak_ridge)[0] == 1
    # …and it WAS eligible: its own utility's run removes it.
    assert _run(oak_ridge) == {"subdomain": oak_ridge.subdomain, "swept": True, "drafts": 1, "files": 1}


# ── 6 · a second run deletes nothing more ────────────────────────────────────


@requires_postgres
@pytest.mark.django_db
def test_a_second_run_deletes_nothing_more(portal_on, clock, audit_rows):
    clock.set("2025-09-01T12:00:00")
    _save(portal_on, MARIA)
    assert _upload(portal_on, PDF, "tenancy-agreement.pdf", token=MARIA).status_code == 200
    clock.set("2025-10-20T12:00:00")
    _save(portal_on, KEPT)

    clock.set("2025-10-31T12:00:00")
    assert _run(portal_on)["drafts"] == 1
    assert len(_deletions(audit_rows)) == 1
    assert _run(portal_on) == {"subdomain": portal_on.subdomain, "swept": True, "drafts": 0, "files": 0}
    assert len(_deletions(audit_rows)) == 1
    assert _drafts(portal_on) == {KEPT}


# ── the schedule is installed, not just correct (law 2) ─────────────────────


def test_the_nightly_entry_is_installed_on_the_celery_app():
    from config.celery import app

    entry = app.conf.beat_schedule.get(draft_cleanup.BEAT_ENTRY)
    assert entry is not None and entry["task"] == draft_cleanup.CLEANUP_TASK
