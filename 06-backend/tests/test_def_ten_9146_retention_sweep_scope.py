# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-TEN-9146 — the audit-log export and the bill print set swept
#          EVERY utility's generated files at the platform default of 3 days.
# Rules:   BR-REP-018 (retention, tenant-configurable) · CR-142-BRC07 `P4.6`
#          (each utility's own `file_retention_days`) · CLAUDE.md hard rule 1
#          (one utility never acts on another's data) · hard-won law 7.
# ───────────────────────────────────────────────────────
"""One utility's export job — or its sweep — never deletes another utility's files.

**Re-stated for S3 on 2026-10-02** (PO ruling, decision log *"EXPORT FILES MOVE
FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*). The shared directory is
gone and so is "sweep on the way into each export": the export jobs delete
nothing, and the daily `export_store.sweep_tenant` does the clean-up. The
defect's rule is kept, and these cases are its proof in the new world:

  * an audit export and a print set run by Brazos Bend delete NOTHING — Lone
    Star's 4-day-old export (kept 7 days) and Brazos Bend's own old one are both
    still there afterwards;
  * Brazos Bend's sweep removes Brazos Bend's own 4-day-old export (kept 3) and
    leaves Lone Star's — the per-utility window, read from each utility;
  * the sweep cannot be called without naming a utility.

⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY (law 7 habit 2).** A sweep that
deleted nothing would keep Lone Star's file too — so the sweep case also asserts
the caller's own old file IS removed. A sweep that used 7 days for everybody
would keep Brazos Bend's 4-day-old file — which the same assertion catches.
"""

import datetime as dt
from datetime import datetime, timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.audit import exports as audit_exports
from apps.billing import print_set
from apps.tenancy import export_store, models as tenancy_models
from apps.tenancy.export_models import JobArtifact

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import seeding_ctx, tenant_ctx

pytestmark = pytest.mark.django_db

BUCKET = "sbh-test-bucket"


def _set_retention(tenant, days):
    with seeding_ctx(tenant):
        row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant_id=tenant.id)
        row.reports = {**(row.reports or {}), "file_retention_days": days}
        row.save(update_fields=["reports", "updated_at"])


def _aged_export(tenant, tmp_path) -> JobArtifact:
    """A stored, 4-day-old export of `tenant`, published through the real store."""
    source = tmp_path / f"{tenant.subdomain}_premises_full-list_current-state_20260928T0900.csv"
    source.write_text("code,name\n", encoding="utf-8")
    with seeding_ctx(tenant):
        job = tenancy_models.Job.objects.create(tenant=tenant, kind="list_export", status="succeeded")
        row = export_store.publish(
            job_id=job.id,
            tenant_id=tenant.id,
            path=source,
            display_name=source.name,
            content_type="text/csv; charset=utf-8",
        )
        JobArtifact.objects.filter(id=row.id).update(
            created_at=timezone.now() - dt.timedelta(days=4)
        )
        row.refresh_from_db()
    return row


def _exists(bucket, key) -> bool:
    try:
        bucket.head_object(Bucket=BUCKET, Key=key)
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture()
def two_utilities(tmp_path, export_bucket, brazos, lonestar):
    _set_retention(lonestar, 7)
    theirs = _aged_export(lonestar, tmp_path)
    mine = _aged_export(brazos, tmp_path)
    return export_bucket, theirs, mine


def test_an_audit_export_deletes_nothing(brazos, two_utilities, tmp_path):
    bucket, theirs, mine = two_utilities
    with seeding_ctx(brazos):
        job = tenancy_models.Job.objects.create(tenant=brazos, kind="audit_export", status="running")
    record = {"id": job.id, "tenant_id": brazos.id, "payload": {"filters": {}, "row_count": 0}}
    with tenant_ctx(brazos):
        audit_exports.run_export_job(record)
    assert _exists(bucket, theirs.storage_key), "Brazos Bend's audit export deleted Lone Star's file"
    assert _exists(bucket, mine.storage_key), "an export job must not sweep — the daily sweep does"


def test_a_print_set_deletes_nothing(brazos, two_utilities):
    bucket, theirs, mine = two_utilities
    with seeding_ctx(brazos):
        job = tenancy_models.Job.objects.create(
            tenant=brazos, kind=print_set.PRINT_SET_JOB, status="running"
        )
    record = {
        "id": job.id,
        "tenant_id": brazos.id,
        "payload": {
            "filters": {},
            "generated_at": datetime(2026, 10, 2, 9, 0, tzinfo=dt_timezone.utc).isoformat(),
            "count": 0,
        },
    }
    with tenant_ctx(brazos):
        print_set.run_print_set_job(record)
    assert _exists(bucket, theirs.storage_key), "Brazos Bend's print set deleted Lone Star's file"
    assert _exists(bucket, mine.storage_key), "an export job must not sweep — the daily sweep does"


def test_the_sweep_removes_only_the_callers_own_expired_files(brazos, two_utilities):
    bucket, theirs, mine = two_utilities
    with tenant_ctx(brazos):
        result = export_store.sweep_tenant(brazos.id)
    assert result.deleted == 1
    assert _exists(bucket, theirs.storage_key), "Brazos Bend's sweep deleted Lone Star's file (kept 7)"
    assert not _exists(bucket, mine.storage_key), "the caller's own file past its 3 days must be swept"


def test_the_sweep_cannot_be_called_without_naming_a_utility():
    """The door the defect came through stays shut in the S3 world."""
    with pytest.raises(TypeError):
        export_store.sweep_tenant()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        export_store.sweep_tenant(None)
