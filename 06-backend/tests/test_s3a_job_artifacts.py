"""`job_artifacts` — the record of one export file (tenancy migration 0055).

PO ruling 2026-10-02 (decision log, *"EXPORT FILES MOVE FROM THE SHARED DISK TO
S3 — THE DESIGN IS APPROVED"*): *"A database record per export file: which
utility, its exact storage path, file name, size and status"* — tenant-scoped,
FORCE row-level security.

The isolation cases run only on PostgreSQL (SQLite has no RLS) and read through
`sbh_rls_probe`, a NOLOGIN NOSUPERUSER NOBYPASSRLS role, because a superuser
bypasses every policy and would prove nothing:

    DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgres://… \
        pytest tests/test_s3a_job_artifacts.py
"""

from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.tenancy.export_models import JobArtifact
from core.tenancy import tenant_context
from tests.isolation_helpers import (  # noqa: F401 — fixtures
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)


@pytest.fixture(autouse=True)
def guc(monkeypatch):
    """The real GUC on PostgreSQL; a recorder on SQLite (see test_cr049_t1)."""
    from django.db import connection as real_connection

    from core import tenancy as core_tenancy
    from tests.test_us_ten_helpers import FakeGucConnection

    if real_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", FakeGucConnection())
    core_tenancy._current_tenant.set(None)
    yield
    core_tenancy._current_tenant.set(None)


@pytest.fixture()
def tenants(db):
    from apps.tenancy.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    alpha = Tenant.objects.create(name="Austin Water", subdomain=f"austin{suffix}")
    beta = Tenant.objects.create(name="Lone Star Water", subdomain=f"lonestar{suffix}")
    return alpha, beta


def _row(tenant, **overrides) -> JobArtifact:
    from apps.tenancy.models import Job

    job = Job.objects.create(tenant=tenant, kind="list_export", status="running")
    fields = dict(
        tenant=tenant,
        job=job,
        tenant_folder=tenant.subdomain,
        storage_key=f"t/{tenant.subdomain}/export/2026/09/{uuid.uuid4()}.csv",
        storage_backend="aws_s3",
        display_name=f"{tenant.subdomain}_premises_full-list_current-state_20260915T1032.csv",
        content_type="text/csv; charset=utf-8",
    )
    fields.update(overrides)
    return JobArtifact.objects.create(**fields)


def test_a_new_row_is_pending_and_points_into_the_export_folder(tenants):
    alpha, _ = tenants
    with tenant_context(alpha.id):
        row = _row(alpha)
    assert row.status == "pending"
    assert row.storage_key.startswith(f"t/{alpha.subdomain}/export/2026/09/")


@pytest.mark.parametrize("module", ["billing", "notifications", "payments", "customers"])
def test_the_database_refuses_a_row_pointing_at_any_other_folder(tenants, module):
    """The PO's *"make sure that you don't delete any other data"*, at the
    database: a sweep driven by these rows cannot be aimed at a bill."""
    alpha, _ = tenants
    with tenant_context(alpha.id), pytest.raises(IntegrityError), transaction.atomic():
        _row(alpha, storage_key=f"t/{alpha.subdomain}/{module}/2026/09/{uuid.uuid4()}.pdf")


def test_stored_requires_its_facts(tenants):
    alpha, _ = tenants
    with tenant_context(alpha.id):
        row = _row(alpha)
        row.status = "stored"
        with pytest.raises(IntegrityError), transaction.atomic():
            row.save()
        row.byte_length, row.content_hash, row.stored_at = 748, "ab" * 32, timezone.now()
        row.save()
    row.refresh_from_db()
    assert row.status == "stored"


def test_an_unknown_status_is_refused(tenants):
    alpha, _ = tenants
    with tenant_context(alpha.id), pytest.raises(IntegrityError), transaction.atomic():
        _row(alpha, status="archived")


@pytest.mark.isolation
@requires_postgres
def test_another_utility_cannot_see_the_row(tenants, rls):  # noqa: F811
    """Through `sbh_rls_probe` (NOSUPERUSER NOBYPASSRLS). The leak this guards is
    the STORAGE KEY: with it, a signed link to another utility's file is one
    call away."""
    rls.assert_is_a_real_proof()
    alpha, beta = tenants
    with tenant_context(alpha.id):
        row = _row(alpha)

    with live_tenant_context(beta.id):
        assert rls.count("job_artifacts") == 0, "LEAK — a second utility sees job_artifacts rows"
    with live_tenant_context(alpha.id):
        assert rls.count("job_artifacts", "id = %s", [str(row.id)]) == 1, (
            "the owning utility cannot see its own row — the fixture proves nothing"
        )
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id','',false)")
    assert rls.count("job_artifacts") == 0


@pytest.mark.isolation
@requires_postgres
def test_row_level_security_is_forced_on_the_table(db):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'job_artifacts'"
        )
        assert cursor.fetchone() == (True, True)
