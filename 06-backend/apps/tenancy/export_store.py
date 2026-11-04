# ── Trace ──────────────────────────────────────────────
# Change:   Export files move from the shared disk to S3 — PO ruling 2026-10-02
#           (decision log "EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE
#           DESIGN IS APPROVED"). Analysis: 09-infra/04-exports-to-s3.md.
# Defect:   DEF-MET-4954 · DEF-TEN-9146 (the sweep's rule: a utility is required,
#           there is no all-utilities form — kept here)
# Rules:    BR-REP-018 / IS-11 (download contract; retention, tenant-configurable,
#           3 days by default) · BR-TEN-043 (retention read at event time) ·
#           CLAUDE.md rule 1 (tenant scoping) · the 2026-08-30 4-hour link ruling
# Tests:    06-backend/tests/test_s3a_export_store.py
# ───────────────────────────────────────────────────────
"""The export store: publish a finished export file, find it, hand it over, sweep it.

Every export job body (the list export, the audit-log export, the bill print
set) writes its file to a SCRATCH folder of its own, then calls `publish()`.
From then on the file is found ONLY through its `job_artifacts` row:

    publish(job_id, tenant_id, path, display_name, content_type)
        → row written `pending` (committed) → bytes uploaded to
          t/<web name>/export/<yyyy>/<mm>/<row id>.<ext> → row `stored`
    for_job(job_id)            the row, under the CALLER's tenant scope
    available(row, now)        stored AND inside the utility's retention, NOW
    download_url(row)          a signed link, 4 hours, naming the file
    stream(row)                the bytes, for a caller that must not redirect
    sweep_tenant(tenant_id)    delete what one utility's retention has run out on

⚠ **NO PATH, NO DISK, NO LISTING.** A row stores the exact key and nothing ever
recomputes it; nothing lists the bucket (`CR-049` decision 4: the table IS the
index). That is why a `pending` row is written BEFORE the upload — see
`export_models.py`.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.tenancy import document_storage, export_storage
from apps.tenancy.export_models import (
    STATUS_DELETED,
    STATUS_PENDING,
    STATUS_STORED,
    JobArtifact,
)

logger = logging.getLogger("smartbillhub.exports")

#: A `pending` row older than this is an upload that never finished (the
#: process died between the row and the bytes). The sweep deletes its key —
#: harmless if nothing was ever uploaded, S3 deletes are idempotent.
ORPHAN_AFTER = dt.timedelta(days=1)

#: Who the row says deleted it — the only process that may.
SWEEP_PROCESS = "export_retention_sweep"


def _tenant_folder(tenant_id: Any) -> str:
    """The utility's web name, read server-side from its own row — never a caller's string."""
    from apps.tenancy import models as tenancy_models

    subdomain = (
        tenancy_models.Tenant.objects.filter(id=tenant_id).values_list("subdomain", flat=True).first()
    )
    if not subdomain:
        raise document_storage.DocumentStorageError(f"no utility {tenant_id!r} to store an export for")
    return str(subdomain)


def publish(
    *, job_id: Any, tenant_id: Any, path: Path, display_name: str, content_type: str
) -> JobArtifact:
    """Store ONE finished export file and return its row (status `stored`).

    ⚠ **IDEMPOTENT PER JOB — A JOB THAT RUNS TWICE WRITES ONE FILE.** A job can
    be run a second time: Celery redelivers with `ACKS_LATE` when a worker dies
    after the upload, a failed job is resumed, and (found by the re-take of
    `DEF-MET-4954`, filed as `DEF-BIL-9152`) the print set's inline fallback ran
    the same job in the web process AND on a worker. The first draft refused
    the second run on the one-row-per-job constraint, which failed a job whose
    file had in fact been made. So a second run REUSES the job's row and its
    key and overwrites the same object: no orphan, nothing to delete, and the
    row id stays the `<file id>` in the key. The insert is attempted inside a
    SAVEPOINT because a refused INSERT poisons the whole PostgreSQL
    transaction (CLAUDE.md law 14) — do not "simplify" it to a bare try/except.
    """
    stage = "resolving the storage settings"
    where = "s3 (not resolved)"
    key = "(no key yet)"
    try:
        store = export_storage.backend()
        where = store.describe()
        stage = "writing the file's record"
        row = _begin(
            job_id=job_id, tenant_id=tenant_id, store=store,
            display_name=display_name, content_type=content_type,
        )
        key = row.storage_key
        stage = "uploading"
        size = Path(path).stat().st_size
        logger.info("export %s: uploading %s byte(s) to %s at %s", job_id, size, where, key)
        length, digest = store.put_file(
            key=key, tenant_folder=row.tenant_folder, path=Path(path), content_type=content_type
        )
    except Exception as exc:
        # ⚠ DEF-TEN-9190 — ONE ERROR LINE, NAMING THE STAGE, THE KEY AND WHERE
        # IT WAS GOING. Until 2026-10-02 a failure here surfaced only as the
        # job's own traceback (and a hang surfaced as nothing at all). The job
        # is failed by `core.jobs.run_job` with the PLAIN sentence raised below,
        # which is what the screen shows; the technical cause is in this line.
        reason = plain_reason(exc)
        logger.error(
            "export %s: publish FAILED while %s - key %s, %s - %s (%s: %s)",
            job_id, stage, key, where, reason, type(exc).__name__, exc,
        )
        raise ExportNotStored(reason) from exc
    row.byte_length, row.content_hash = length, digest
    row.stored_at, row.status = timezone.now(), STATUS_STORED
    row.save(update_fields=["byte_length", "content_hash", "stored_at", "status"])
    logger.info("export %s: stored %s byte(s) at %s (%s)", job_id, length, key, where)
    return row


class ExportNotStored(document_storage.DocumentStorageError):
    """The export file did not reach storage. Its message is the plain reason a clerk reads."""


def plain_reason(exc: BaseException) -> str:
    """A short sentence for the screen, from whatever stopped the upload (DEF-TEN-9190).

    Read by the job's `error` field and so by the Export control. The full
    technical cause is logged beside it at ERROR; this is only the part a
    clerk can act on, or pass on.
    """
    name = type(exc).__name__
    text = str(exc)
    code = ""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = str((response.get("Error") or {}).get("Code") or "")
    if isinstance(exc, document_storage.StorageNotConfigured):
        return "File storage is not set up."
    if isinstance(exc, export_storage.ExportObjectMissing):
        return "File missing from storage after upload."
    if name in {"NoCredentialsError", "PartialCredentialsError", "CredentialRetrievalError"}:
        return "No storage credentials on the worker."
    if name in {"EndpointConnectionError", "ConnectTimeoutError", "ConnectionClosedError"}:
        return "Could not reach file storage."
    if name in {"ReadTimeoutError"} or "timed out" in text.lower():
        return "File storage did not answer."
    if code in {"AccessDenied", "403", "Forbidden"} or "AccessDenied" in text or "403" in text:
        return "File storage refused the upload."
    if code == "NoSuchBucket" or "NoSuchBucket" in text:
        return "The storage bucket does not exist."
    if "Could not connect" in text or "Connect timeout" in text:
        return "Could not reach file storage."
    return "The file could not be stored."


def _begin(
    *, job_id: Any, tenant_id: Any, store: Any, display_name: str, content_type: str
) -> JobArtifact:
    """The job's `pending` row — written (or reused) BEFORE any byte is uploaded."""
    from django.db import IntegrityError, transaction

    from core.dbfields import uuid7

    folder = _tenant_folder(tenant_id)
    export_storage.content_disposition(display_name)  # refuse a bad name BEFORE the row
    row = JobArtifact.objects.filter(job_id=job_id).first()
    if row is None:
        file_id = uuid7()
        try:
            with transaction.atomic():
                row = JobArtifact.objects.create(
                    id=file_id,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    tenant_folder=folder,
                    storage_key=export_storage.export_key(
                        tenant_folder=folder,
                        file_id=file_id,
                        moment=timezone.now(),
                        extension=document_storage.extension_for(content_type),
                    ),
                    storage_backend=store.name,
                    display_name=display_name,
                    content_type=content_type,
                    status=STATUS_PENDING,
                )
        except IntegrityError:
            # A concurrent run of the same job wrote the row first: use it.
            row = JobArtifact.objects.get(job_id=job_id)
    if row.status != STATUS_PENDING or row.display_name != display_name:
        row.status, row.display_name, row.content_type = STATUS_PENDING, display_name, content_type
        row.byte_length = row.content_hash = row.stored_at = None
        row.deleted_at = row.deleted_by_process = None
        row.save(
            update_fields=[
                "status", "display_name", "content_type", "byte_length",
                "content_hash", "stored_at", "deleted_at", "deleted_by_process",
            ]
        )
    return row


def for_job(job_id: Any) -> JobArtifact | None:
    """The row for `job_id` under the CALLER's tenant scope, or None.

    Tenant-scoped twice, as every read here is: the explicit filter (every
    database) and RLS (PostgreSQL). Another utility's job id is simply absent.
    """
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        return None
    try:
        return JobArtifact.objects.filter(tenant_id=tenant_id, job_id=job_id).first()
    except (ValueError, TypeError):
        return None


def statuses_for_jobs(job_ids: list[Any]) -> dict[str, str]:
    """{job id: row status} for one page of jobs — ONE query, not one per row."""
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None or not job_ids:
        return {}
    rows = JobArtifact.objects.filter(tenant_id=tenant_id, job_id__in=job_ids).values_list(
        "job_id", "status"
    )
    return {str(job): status for job, status in rows}


def available(row: JobArtifact | None, *, now: dt.datetime | None = None) -> bool:
    """Stored, and inside the utility's `file_retention_days` evaluated NOW.

    BR-TEN-043: retention is read at event time, never stamped on the row, so
    lowering the setting makes yesterday's file unavailable the moment it is
    saved — before the sweep has removed anything.
    """
    if row is None or row.status != STATUS_STORED:
        return False
    from apps.tenancy import exports

    moment = now or timezone.now()
    days = exports.artifact_retention_days(row.tenant_id)
    return row.created_at >= moment - dt.timedelta(days=days)


def download_url(row: JobArtifact) -> str:
    """A signed link to this one file — 4 hours (the 2026-08-30 ruling's cap)."""
    return export_storage.backend().read_url(
        key=row.storage_key,
        tenant_folder=row.tenant_folder,
        filename=row.display_name,
        content_type=row.content_type,
    )


def object_exists(row: JobArtifact) -> bool:
    """Does the bucket hold this row's file now? Logged at ERROR when it does not (DEF-TEN-9190)."""
    present = export_storage.backend().exists(key=row.storage_key, tenant_folder=row.tenant_folder)
    if not present:
        logger.error(
            "export %s: the row says stored but the bucket does not answer for %s - "
            "the download is refused with the plain 404",
            row.job_id,
            row.storage_key,
        )
    return present


def stream(row: JobArtifact) -> Iterator[bytes]:
    """The file's bytes in chunks — for the report-delivery link, which streams."""
    return export_storage.backend().open_stream(key=row.storage_key, tenant_folder=row.tenant_folder)


@dataclasses.dataclass
class SweepResult:
    deleted: int = 0
    orphans: int = 0
    refused: int = 0


def sweep_tenant(tenant_id: Any, *, now: dt.datetime | None = None) -> SweepResult:
    """Delete ONE utility's export files its own retention has run out on.

    ⚠ **`tenant_id` IS REQUIRED AND THERE IS NO ALL-UTILITIES FORM** — the rule
    `DEF-TEN-9146` set for the disk sweep, kept here. The beat task fans out one
    call per utility; each call reads that utility's own `file_retention_days`.

    ⚠ **IT CAN DELETE NOTHING BUT AN EXPORT OF THIS UTILITY**, three ways
    (PO 2026-10-02: *"make sure that you don't delete any other data"*):
      1. it acts only on `job_artifacts` rows of this utility — it never lists;
      2. `export_storage.delete` refuses a key not under
         `t/<this utility's CURRENT web name>/export/` (a renamed utility's old
         keys are therefore refused and counted, never deleted — the safe
         direction, 09-infra/04 R6);
      3. IAM grants delete on `t/*/export/*` only (02-aws-runbook.md).

    A row is STAMPED `deleted`, never removed, so run history keeps it as
    *expired*. Best-effort per row: one refusal or failure is logged and counted
    and never stops the rest.
    """
    if tenant_id is None:
        raise TypeError("sweep_tenant needs a utility; there is no all-utilities sweep (DEF-TEN-9146)")
    from apps.tenancy import exports

    moment = now or timezone.now()
    folder = _tenant_folder(tenant_id)
    days = exports.artifact_retention_days(tenant_id)
    expired = Q(status=STATUS_STORED, created_at__lt=moment - dt.timedelta(days=days))
    orphaned = Q(status=STATUS_PENDING, created_at__lt=moment - ORPHAN_AFTER)
    result = SweepResult()
    store = None
    for row in JobArtifact.objects.filter(Q(tenant_id=tenant_id) & (expired | orphaned)).order_by(
        "created_at"
    ):
        if store is None:
            store = export_storage.backend()
        try:
            store.delete(key=row.storage_key, tenant_folder=folder)
        except export_storage.ExportKeyRefused:
            logger.warning(
                "export sweep refused %s for %s: not under its current export folder",
                row.storage_key,
                folder,
            )
            result.refused += 1
            continue
        except Exception:  # noqa: BLE001 — one failure never stops the sweep
            logger.exception("export sweep could not delete %s", row.storage_key)
            continue
        if row.status == STATUS_PENDING:
            result.orphans += 1
        else:
            result.deleted += 1
        row.status, row.deleted_at, row.deleted_by_process = STATUS_DELETED, moment, SWEEP_PROCESS
        row.save(update_fields=["status", "deleted_at", "deleted_by_process"])
    return result


# ── Lifecycle ─────────────────────────────────────────────
# packet: exports-to-S3 build step 3 (09-infra/04-exports-to-s3.md §6)
# generated: 2026-10-02 by the s3a lane
# checklist: A✔ B✔ C✔ D=deferred(readers, step 5) E=n/a F✔ G✔ H=n/a
# gates: tests/test_s3a_export_store.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
