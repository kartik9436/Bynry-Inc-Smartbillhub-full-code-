"""An export never says "ready" without its file, and never fails in silence.

DEF-TEN-9190 (reported 2026-10-02 from a real deployment, 2.455.0): a Premises
export built 73 rows and then sat in `running` with nothing in any log, and the
developer found no `export/` folder in the bucket. DEF-TEN-9189 is its front-end
half (the Download link resolved against the static app host). These tests hold
the server half:

  * the S3 client carries explicit timeouts and a bounded retry budget;
  * publish fails the JOB with a plain reason, and logs ONE error line naming the
    stage, the key and where it was going — for a refused upload, for a bucket
    that does not exist, and for an upload that "returned" with no object;
  * a stalled export is failed by the ten-minute sweep, and a bill run is not;
  * a worker refuses to start with no export storage, and says where it writes
    when it has some — including when it cannot reach it;
  * the download can answer the signed link as JSON, which is how the screen
    asks for it now, and a SUCCEEDED job with no file is logged at ERROR.
"""

from __future__ import annotations

import datetime as dt
import io
import logging
import uuid

import pytest
from django.utils import timezone

from apps.tenancy import export_storage, export_store, export_sweep
from apps.tenancy import exports as export_kernel
from apps.tenancy.export_models import JobArtifact
from core import jobs as core_jobs
from core import storage_guard
from core.tenancy import tenant_context
from tests.test_us_idn_helpers import idn  # noqa: F401 (fixture import)


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
def wired_store():
    from apps.tenancy import services as tenancy_services

    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(None)
    yield
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


@pytest.fixture()
def utility(db):
    from apps.tenancy.models import Tenant

    return Tenant.objects.create(name="Austin Water", subdomain=f"austin-{uuid.uuid4().hex[:6]}")


def _csv(tmp_path, tenant):
    path = tmp_path / f"{tenant.subdomain}_premises_full-list_current-state_20261002T1826.csv"
    path.write_bytes(b"premise_no\r\nP-00001\r\n")
    return path


class _Wrapping:
    """The emulated client, with ONE behaviour replaced."""

    def __init__(self, inner, **replace):
        self._inner = inner
        self._replace = replace

    def __getattr__(self, name):
        if name in self._replace:
            return self._replace[name]
        return getattr(self._inner, name)


def _client_error(code: str, operation: str):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


def _run_export_job(tenant, path):
    """A real job record, run through `core.jobs.run_job` the way a worker does."""
    with tenant_context(tenant.id):
        record = core_jobs.enqueue(export_kernel.LIST_EXPORT_JOB, payload={"resource": "premises"})
        with pytest.raises(export_store.ExportNotStored):
            core_jobs.run_job(
                record["id"],
                lambda started: export_kernel.finish_artifact(
                    started["id"], path, tenant_id=tenant.id
                ),
            )
        return core_jobs.current(record["id"])


# ── the client ───────────────────────────────────────────────────────────────
def test_the_s3_client_has_explicit_timeouts_and_a_bounded_retry_budget(settings):
    """boto3's own defaults are 60 s + 60 s and five attempts: 311 s measured
    against a listener that accepts and never answers. Ours are settings."""
    from apps.tenancy import document_storage

    config = document_storage.client_config()
    assert config.connect_timeout == 5
    assert config.read_timeout == 60
    assert config.retries == {"max_attempts": 3, "mode": "standard"}

    settings.DOCUMENT_STORAGE_CONNECT_TIMEOUT = 2
    assert document_storage.client_config().connect_timeout == 2

    # And the client every S3 call is made through actually carries it.
    settings.DOCUMENT_STORAGE_ENDPOINT_URL = "http://127.0.0.1:9"
    settings.DOCUMENT_STORAGE_REGION = "us-east-1"
    client = document_storage._default_client()
    assert client.meta.config.connect_timeout == 2
    assert client.meta.config.read_timeout == 60
    # botocore counts RETRIES in `max_attempts`: 3 retries is 4 calls in all.
    assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 4}


# ── publish fails loudly, with a plain reason ────────────────────────────────
def test_a_refused_upload_fails_the_job_with_a_plain_reason_and_one_error_line(
    utility, tmp_path, wired_store, export_bucket, caplog
):
    def refuse(*_args, **_kwargs):
        raise _client_error("AccessDenied", "PutObject")

    export_storage.set_client_factory(lambda: _Wrapping(export_bucket, upload_file=refuse))
    caplog.set_level(logging.INFO, logger="smartbillhub.exports")

    job = _run_export_job(utility, _csv(tmp_path, utility))

    assert job["status"] == core_jobs.FAILED
    assert job["error"] == "ExportNotStored: File storage refused the upload."
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1, errors
    row = JobArtifact.objects.get(job_id=job["id"])
    assert "publish FAILED while uploading" in errors[0]
    assert row.storage_key in errors[0]
    assert "s3://sbh-test-bucket" in errors[0]
    assert "AccessDenied" in errors[0]
    # Nothing calls it stored: the row is the pending one the sweep collects.
    assert row.status == "pending"


def test_a_bucket_that_does_not_exist_fails_the_job(
    utility, tmp_path, wired_store, export_bucket, settings
):
    settings.DOCUMENT_STORAGE_BUCKET = "no-such-bucket-exdl"
    job = _run_export_job(utility, _csv(tmp_path, utility))
    assert job["status"] == core_jobs.FAILED
    assert job["error"] == "ExportNotStored: The storage bucket does not exist."


def test_an_upload_that_returns_without_an_object_is_never_stored(
    utility, tmp_path, wired_store, export_bucket
):
    """The case a developer cannot see from the job: success with no file."""
    export_storage.set_client_factory(
        lambda: _Wrapping(export_bucket, upload_file=lambda *a, **k: None)
    )
    job = _run_export_job(utility, _csv(tmp_path, utility))
    assert job["status"] == core_jobs.FAILED
    assert job["error"] == "ExportNotStored: File missing from storage after upload."
    assert JobArtifact.objects.get(job_id=job["id"]).status == "pending"


def test_an_unreachable_endpoint_fails_the_job_within_the_client_budget(
    utility, tmp_path, wired_store, settings
):
    """A listener that accepts and never answers — the worst network case."""
    import socket
    import time

    import boto3

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    settings.DOCUMENT_STORAGE_CONNECT_TIMEOUT = 1
    settings.DOCUMENT_STORAGE_READ_TIMEOUT = 1
    settings.DOCUMENT_STORAGE_MAX_ATTEMPTS = 1
    from apps.tenancy import document_storage

    export_storage.set_client_factory(
        lambda: boto3.client(
            "s3",
            endpoint_url=f"http://127.0.0.1:{port}",
            region_name="us-east-1",
            aws_access_key_id="x",
            aws_secret_access_key="y",
            config=document_storage.client_config(),
        )
    )
    started = time.monotonic()
    try:
        job = _run_export_job(utility, _csv(tmp_path, utility))
    finally:
        listener.close()
    assert time.monotonic() - started < 30
    assert job["status"] == core_jobs.FAILED
    assert job["error"] == "ExportNotStored: File storage did not answer."


def test_a_stored_export_logs_each_stage(utility, tmp_path, export_bucket, caplog):
    from apps.tenancy.models import Job

    caplog.set_level(logging.INFO, logger="smartbillhub.exports")
    job = Job.objects.create(tenant=utility, kind="list_export", status="running")
    with tenant_context(utility.id):
        row = export_store.publish(
            job_id=job.id,
            tenant_id=utility.id,
            path=_csv(tmp_path, utility),
            display_name=f"{utility.subdomain}_premises_full-list_current-state_20261002T1826.csv",
            content_type="text/csv; charset=utf-8",
        )
    lines = [r.getMessage() for r in caplog.records]
    assert any(f"export {job.id}: uploading" in line and row.storage_key in line for line in lines)
    assert any(f"export {job.id}: stored" in line and row.storage_key in line for line in lines)


# ── the stall sweep ──────────────────────────────────────────────────────────
def test_a_stalled_export_is_failed_and_a_bill_run_is_not(
    utility, wired_store, caplog, monkeypatch
):
    from apps.tenancy.models import Job

    old = timezone.now() - dt.timedelta(minutes=31)
    stalled = Job.objects.create(tenant=utility, kind="list_export", status="running")
    fresh = Job.objects.create(tenant=utility, kind="list_export", status="running")
    bill_run = Job.objects.create(tenant=utility, kind="billing.run.calculate", status="running")
    Job.objects.filter(id__in=[stalled.id, bill_run.id]).update(updated_at=old)
    caplog.set_level(logging.ERROR, logger="smartbillhub.exports")

    result = export_sweep.fail_stalled_one(utility.subdomain)

    assert result["failed"] == 1
    for job, status in ((stalled, "failed"), (fresh, "running"), (bill_run, "running")):
        job.refresh_from_db()
        assert job.status == status, job.kind
    stalled.refresh_from_db()
    assert stalled.error == export_sweep.STALLED_ERROR
    assert any(str(stalled.id) in r.getMessage() for r in caplog.records)


def test_the_stall_sweep_is_on_the_beat_every_ten_minutes():
    entry = export_sweep.beat_schedule()[export_sweep.STALL_ENTRY]
    assert entry["task"] == export_sweep.STALL_TASK
    assert "*/10" in str(entry["schedule"])


# ── the worker says where it writes, and refuses to start with nowhere ──────
def test_a_process_with_no_bucket_refuses_to_start(settings):
    settings.DEBUG = False
    settings.DOCUMENT_STORAGE_BUCKET = ""
    out = io.StringIO()
    with pytest.raises(SystemExit) as stopped:
        storage_guard.enforce_export_storage_at_startup(process="celery worker", stream=out)
    assert stopped.value.code == 1
    assert "NOT CONFIGURED" in out.getvalue()
    assert "REFUSES TO START" in out.getvalue()


def test_a_configured_worker_says_where_it_writes(export_bucket):
    out = io.StringIO()
    storage_guard.enforce_export_storage_at_startup(process="celery worker", stream=out)
    assert "export storage: s3://sbh-test-bucket" in out.getvalue()
    assert "reachable" in out.getvalue()
    assert "UNREACHABLE" not in out.getvalue()


def test_a_bucket_name_s3_does_not_know_is_said_at_start(export_bucket, settings, caplog):
    settings.DOCUMENT_STORAGE_BUCKET = "exdl-no-such-bucket"
    caplog.set_level(logging.INFO, logger="smartbillhub.exports")
    storage_guard.enforce_export_storage_at_startup(process="celery worker")
    lines = [(r.levelno, r.getMessage()) for r in caplog.records]
    assert any(level == logging.ERROR and "BUCKET NOT FOUND" in text for level, text in lines), lines


def test_an_unreachable_bucket_is_said_at_start_and_does_not_block_it(settings):
    import boto3

    from apps.tenancy import document_storage

    settings.DOCUMENT_STORAGE_CONNECT_TIMEOUT = 1
    settings.DOCUMENT_STORAGE_MAX_ATTEMPTS = 1
    export_storage.set_client_factory(
        lambda: boto3.client(
            "s3",
            endpoint_url="http://127.0.0.1:9",  # nothing listens on discard
            region_name="us-east-1",
            aws_access_key_id="x",
            aws_secret_access_key="y",
            config=document_storage.client_config(),
        )
    )
    out = io.StringIO()
    storage_guard.enforce_export_storage_at_startup(process="celery worker", stream=out)
    assert "UNREACHABLE from this process" in out.getvalue()


def test_the_celery_worker_runs_the_check_when_it_starts():
    from celery.signals import worker_init

    import config.celery  # noqa: F401 — connects the receiver

    names = [getattr(ref(), "__name__", "") for _key, ref in worker_init.receivers]
    assert "_export_storage_at_start" in names


# ── the download refuses the same plain 404, and the LOG says which ─────────
def test_a_succeeded_job_with_no_file_is_a_plain_404_and_an_error_line(idn, caplog, wired_store):
    from tests.test_be_export_download import ALEX, queued_job
    from tests.test_us_idn_helpers import api_get, signed_in_client

    idn.seed_silvercreek()
    record = queued_job(idn.silvercreek)
    with tenant_context(idn.silvercreek.id):
        core_jobs.start(record["id"])
        core_jobs.succeed(record["id"], result_link=export_kernel.download_path(record["id"]))
    caplog.set_level(logging.ERROR, logger="smartbillhub.exports")

    answer = api_get(signed_in_client(*ALEX), export_kernel.download_path(record["id"]))

    assert answer.status_code == 404
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(
        record["id"] in line and "no file was ever recorded" in line for line in errors
    ), errors


def test_a_stored_row_whose_object_is_gone_is_a_404_not_a_redirect_to_s3s_error(
    idn, caplog, wired_store, export_bucket, tmp_path
):
    from tests.test_be_export_download import ALEX, finished_job
    from tests.test_us_idn_helpers import api_get, signed_in_client

    idn.seed_silvercreek()
    record = finished_job(idn.silvercreek, tmp_path, kind=export_kernel.LIST_EXPORT_JOB)
    row = JobArtifact.objects.get(job_id=record["id"])
    alex = signed_in_client(*ALEX)
    assert api_get(alex, export_kernel.download_path(record["id"])).status_code == 302

    export_bucket.delete_object(Bucket="sbh-test-bucket", Key=row.storage_key)
    caplog.set_level(logging.ERROR, logger="smartbillhub.exports")
    answer = api_get(alex, export_kernel.download_path(record["id"]))

    assert answer.status_code == 404
    assert any(row.storage_key in r.getMessage() for r in caplog.records), caplog.records
