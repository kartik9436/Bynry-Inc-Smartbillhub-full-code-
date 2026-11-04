"""The export store — `apps/tenancy/export_store.py`, on an S3 emulator.

PO ruling 2026-10-02 (decision log, *"EXPORT FILES MOVE FROM THE SHARED DISK TO
S3 — THE DESIGN IS APPROVED"*):
  * *"A database record per export file"* — publish writes it, readers use it;
  * *"Once a day, for each utility, the system deletes exports older than that
    utility's own setting (3 days by default) … but make sure that you don't
    delete any other data"* — the sweep below.
The sweep keeps `DEF-TEN-9146`'s rule: a utility is required, and one
utility's sweep never touches another's files.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.tenancy import document_storage, export_storage, export_store
from apps.tenancy.export_models import JobArtifact
from core.tenancy import tenant_context

BUCKET = "sbh-test-bucket"


@pytest.fixture(autouse=True)
def guc(monkeypatch):
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

    suffix = uuid.uuid4().hex[:6]
    austin = Tenant.objects.create(name="Austin Water", subdomain=f"austin-water-{suffix}")
    lone = Tenant.objects.create(name="Lone Star Water", subdomain=f"lone-star-{suffix}")
    return austin, lone


def _keep_days(tenant, days: int) -> None:
    from apps.tenancy.models import TenantSettings

    settings_row, _ = TenantSettings.objects.get_or_create(tenant=tenant)
    settings_row.reports = {**(settings_row.reports or {}), "file_retention_days": days}
    settings_row.save()


def _publish(tenant, tmp_path, *, body=b"premise_no\r\nP-00001\r\n", name=None, age_days=0):
    from apps.tenancy.models import Job

    job = Job.objects.create(tenant=tenant, kind="list_export", status="running")
    source = tmp_path / f"{uuid.uuid4().hex}.csv"
    source.write_bytes(body)
    with tenant_context(tenant.id):
        row = export_store.publish(
            job_id=job.id,
            tenant_id=tenant.id,
            path=source,
            display_name=name or f"{tenant.subdomain}_premises_full-list_current-state_20260915T1032.csv",
            content_type="text/csv; charset=utf-8",
        )
    if age_days:
        JobArtifact.objects.filter(id=row.id).update(
            created_at=timezone.now() - dt.timedelta(days=age_days)
        )
        row.refresh_from_db()
    return job, row


def _exists(client, key) -> bool:
    try:
        client.head_object(Bucket=BUCKET, Key=key)
        return True
    except Exception:  # noqa: BLE001
        return False


def test_publish_stores_the_file_under_the_utilitys_export_folder(tenants, tmp_path, export_bucket):
    austin, _ = tenants
    job, row = _publish(austin, tmp_path)
    assert row.status == "stored"
    assert row.storage_key == f"t/{austin.subdomain}/export/{row.created_at:%Y/%m}/{row.id}.csv"
    assert row.byte_length == len(b"premise_no\r\nP-00001\r\n")
    assert export_bucket.get_object(Bucket=BUCKET, Key=row.storage_key)["Body"].read() == (
        b"premise_no\r\nP-00001\r\n"
    )
    with tenant_context(austin.id):
        assert export_store.for_job(job.id) == row
        assert export_store.available(row)


def test_a_job_that_runs_twice_writes_one_file(tenants, tmp_path, export_bucket):
    """`DEF-BIL-9152`'s shape, and Celery's redelivery: the SAME job publishes
    twice. One row, one key, the second run's bytes — never a refused second
    run of a job whose file was in fact made."""
    austin, _ = tenants
    job, first = _publish(austin, tmp_path, body=b"premise_no\r\nP-00001\r\n")
    second_source = tmp_path / "again.csv"
    second_source.write_bytes(b"premise_no\r\nP-00002\r\n")
    with tenant_context(austin.id):
        second = export_store.publish(
            job_id=job.id,
            tenant_id=austin.id,
            path=second_source,
            display_name=first.display_name,
            content_type="text/csv; charset=utf-8",
        )
    assert JobArtifact.objects.filter(job_id=job.id).count() == 1
    assert second.id == first.id and second.storage_key == first.storage_key
    assert second.status == "stored"
    body = export_bucket.get_object(Bucket=BUCKET, Key=second.storage_key)["Body"].read()
    assert body == b"premise_no\r\nP-00002\r\n"


def test_another_utility_cannot_find_the_row(tenants, tmp_path):
    austin, lone = tenants
    job, _ = _publish(austin, tmp_path)
    with tenant_context(lone.id):
        assert export_store.for_job(job.id) is None
        assert export_store.statuses_for_jobs([job.id]) == {}


def test_a_file_past_retention_is_unavailable_before_the_sweep_runs(tenants, tmp_path):
    """BR-TEN-043 — retention is read now; lowering it hides the file at once."""
    austin, _ = tenants
    _, row = _publish(austin, tmp_path, age_days=2)
    with tenant_context(austin.id):
        assert export_store.available(row)  # 2 days old, kept 3
        _keep_days(austin, 1)
        assert not export_store.available(row)


def test_the_sweep_deletes_one_utilitys_expired_exports_and_nothing_else(
    tenants, tmp_path, export_bucket
):
    austin, lone = tenants
    _keep_days(lone, 7)
    _, old = _publish(austin, tmp_path, age_days=4)
    _, fresh = _publish(austin, tmp_path, age_days=1)
    _, theirs = _publish(lone, tmp_path, age_days=4)  # Lone Star keeps 7 days
    bill_key = document_storage.key_for(
        tenant_folder=austin.subdomain,
        module="billing",
        document_id=uuid.uuid4(),
        moment=timezone.now() - dt.timedelta(days=30),
        extension="pdf",
    )
    notice_key = bill_key.replace("/billing/", "/notifications/")
    for key in (bill_key, notice_key):
        export_bucket.put_object(Bucket=BUCKET, Key=key, Body=b"%PDF-1.7")

    with tenant_context(austin.id):
        result = export_store.sweep_tenant(austin.id)

    assert (result.deleted, result.orphans, result.refused) == (1, 0, 0)
    old.refresh_from_db()
    assert old.status == "deleted" and old.deleted_by_process == export_store.SWEEP_PROCESS
    assert not _exists(export_bucket, old.storage_key)
    assert _exists(export_bucket, fresh.storage_key)
    assert _exists(export_bucket, theirs.storage_key), "another utility's export was deleted"
    assert _exists(export_bucket, bill_key), "a BILL was deleted by the export sweep"
    assert _exists(export_bucket, notice_key), "a NOTICE was deleted by the export sweep"


def test_the_sweep_refuses_a_row_whose_key_is_not_this_utilitys_export_folder(
    tenants, tmp_path, export_bucket
):
    """A row pointing outside `t/<this utility>/export/` — here another
    utility's export folder, the only foreign shape the database's own check
    lets a row hold — is refused by the adapter, counted, and left alone."""
    austin, lone = tenants
    _, theirs = _publish(lone, tmp_path)
    from apps.tenancy.models import Job

    job = Job.objects.create(tenant=austin, kind="list_export", status="succeeded")
    with tenant_context(austin.id):
        JobArtifact.objects.create(
            tenant=austin,
            job=job,
            tenant_folder=austin.subdomain,
            storage_key=theirs.storage_key,
            storage_backend="aws_s3",
            display_name="x.csv",
            content_type="text/csv",
            status="stored",
            byte_length=1,
            content_hash="0" * 64,
            stored_at=timezone.now(),
        )
        JobArtifact.objects.filter(job=job).update(created_at=timezone.now() - dt.timedelta(days=9))
        result = export_store.sweep_tenant(austin.id)
    assert result.refused == 1 and result.deleted == 0
    assert _exists(export_bucket, theirs.storage_key)


def test_an_orphaned_upload_is_swept_after_a_day(tenants, tmp_path, export_bucket):
    austin, _ = tenants
    from apps.tenancy.models import Job

    job = Job.objects.create(tenant=austin, kind="list_export", status="failed")
    key = export_storage.export_key(
        tenant_folder=austin.subdomain, file_id=uuid.uuid4(), moment=timezone.now(), extension="csv"
    )
    export_bucket.put_object(Bucket=BUCKET, Key=key, Body=b"half")
    with tenant_context(austin.id):
        JobArtifact.objects.create(
            tenant=austin,
            job=job,
            tenant_folder=austin.subdomain,
            storage_key=key,
            storage_backend="aws_s3",
            display_name="x.csv",
            content_type="text/csv",
        )
        JobArtifact.objects.filter(job=job).update(created_at=timezone.now() - dt.timedelta(hours=25))
        result = export_store.sweep_tenant(austin.id)
    assert result.orphans == 1
    assert not _exists(export_bucket, key)


def test_the_sweep_needs_a_utility():
    with pytest.raises(TypeError):
        export_store.sweep_tenant()  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="no all-utilities sweep"):
        export_store.sweep_tenant(None)
