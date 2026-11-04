# ── Trace ──────────────────────────────────────────────
# Change:   Export files move from the shared disk to S3 — PO ruling 2026-10-02
#           (decision log "EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE
#           DESIGN IS APPROVED"): *"A database record per export file: which
#           utility, its exact storage path, file name, size and status"*.
# Defect:   DEF-MET-4954 (the job record held the WRITING container's disk path)
# Rules:    CLAUDE.md rule 1 (tenant scoping, RLS FORCE — migration 0055) ·
#           BR-REP-018 (retention) · CR-160-BRC10 (the key is written verbatim)
# Tests:    06-backend/tests/test_s3a_job_artifacts.py
# ───────────────────────────────────────────────────────
"""`job_artifacts` — the record of ONE export file, and the only way to find it.

**What replaced the disk path.** Until 2026-10-02 an export job wrote
`payload["artifact_path"]` — an absolute path on the disk of whichever container
ran it, which is the whole of `DEF-MET-4954`. Now the job body writes THIS row,
and every reader (the Download button, the report-delivery link, the run-history
screen, the retention sweep) resolves the file through it. Nothing ever lists
the bucket: this table IS the index.

**Why not a `stored_documents` row.** That table refuses every UPDATE and DELETE
(migration 0026) — it holds legal documents. An export is deleted when its
utility's `file_retention_days` runs out, so its row must be able to say so.

**The row is written FIRST, as `pending`, then the bytes are uploaded, then it
becomes `stored`.** The opposite order (`document_store`'s, which is right for
a document that can never be deleted) would leave an uploaded object with no
row if the process died between the two — and with "never list the bucket" that
object could never be found again. A `pending` row older than a day is exactly
how the sweep finds one.

**The row is never deleted — it is STAMPED `deleted`.** Run history keeps
showing who exported what and when, as *expired*, after the file has gone.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

STATUS_PENDING = "pending"  # row written, bytes not (yet) uploaded
STATUS_STORED = "stored"  # the object exists at storage_key
STATUS_DELETED = "deleted"  # the object was removed by the retention sweep
STATUSES = (STATUS_PENDING, STATUS_STORED, STATUS_DELETED)


class JobArtifact(models.Model):
    """One export file of one job, stored at `t/<web name>/export/…`."""

    #: Also the `<file id>` in the key — one id for the row and the object.
    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    job = models.OneToOneField(
        "tenancy.Job", on_delete=models.PROTECT, db_column="job_id", related_name="artifact"
    )
    #: The utility's web name AT WRITE TIME. The key is built from it and the
    #: sweep's guard checks the key against the utility's CURRENT web name, so
    #: a rename leaves the old file refused (safe direction) rather than the
    #: guard loosened (09-infra/04 R6).
    tenant_folder = models.TextField()
    #: Written verbatim, never recomputed — `t/<web name>/export/<yyyy>/<mm>/<id>.<ext>`.
    storage_key = models.TextField()
    storage_backend = models.TextField()
    #: The IS-11 filename the writer composed — what the browser saves it as.
    display_name = models.TextField()
    content_type = models.TextField()
    byte_length = models.BigIntegerField(null=True, blank=True)
    content_hash = models.TextField(null=True, blank=True)  # sha256, lowercase hex
    status = models.TextField(default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    stored_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by_process = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "job_artifacts"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=STATUSES), name="ck_job_artifacts_status"
            ),
            # The database's own belt for the PO's "make sure that you don't
            # delete any other data": a row can only ever point INTO an export
            # folder, so a sweep driven by these rows cannot be pointed at a
            # bill. The adapter checks the same thing against the utility.
            models.CheckConstraint(
                condition=Q(storage_key__regex=r"^t/[a-z0-9][a-z0-9-]{1,61}[a-z0-9]/export/"),
                name="ck_job_artifacts_export_key",
            ),
            models.CheckConstraint(
                # `stored` must carry its facts; `pending` has none yet, and a
                # `deleted` row may be an orphaned upload that never had any.
                condition=~Q(status=STATUS_STORED)
                | Q(byte_length__isnull=False, content_hash__isnull=False, stored_at__isnull=False),
                name="ck_job_artifacts_stored_facts",
            ),
            models.UniqueConstraint(fields=["tenant", "storage_key"], name="uq_job_artifacts_key"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"], name="ix_job_artifacts_sweep"),
        ]

    def __str__(self) -> str:  # pragma: no cover - admin/debug only
        return f"{self.display_name} ({self.status})"


# ── Lifecycle ─────────────────────────────────────────────
# packet: exports-to-S3 build step 2 (09-infra/04-exports-to-s3.md §6)
# generated: 2026-10-02 by the s3a lane
# checklist: A✔ B✔ C✔ D=deferred(read by the store, step 3) E=n/a F✔ G✔ H=deferred(PO 2026-08-09 — RLS migration 0055 HUMAN-REVIEW-PENDING)
# gates: tests/test_s3a_job_artifacts.py (isolation proved on PostgreSQL as a NOSUPERUSER NOBYPASSRLS role)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
