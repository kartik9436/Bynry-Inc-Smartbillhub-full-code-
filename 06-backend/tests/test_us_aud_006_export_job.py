# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-006 (EP-AUD-02 — the S61 CSV export: the JOB BODY half. The
#           accept/cap/self-audit TCs stay in tests/test_us_aud_004_006_viewer.py;
#           this file is TC-1's file — the file that actually gets written.)
#           Screens: S61
# Rules:    BR-AUD-014 (IS-9/IS-11 CSV under BR-SHL-016 guards; 50k cap at
#           accept time) · BR-AUD-013 (the same bounded query the list serves) ·
#           BR-AUD-007 (tenant-scoped only) · BR-AUD-006 (masked values written
#           exactly as stored) · BR-AUD-003 (null actor = system) ·
#           BR-REP-018 (IS-11 contract + 3-day retention)
# ───────────────────────────────────────────────────────
"""US-AUD-006 TCs for the export job body (apps/audit/exports.py).

Rides the identity plumbing like the viewer tests: S61 is role law, so the
export is requested by the real fixture actors over HTTP and the server
decides. JOBS_EAGER is turned on per test — that is the R1 path under test
(202 → the job runs → the file exists), and the test settings keep it off by
default so the rest of the suite can run enqueue and run as separate steps.

The artifacts directory is redirected to tmp_path in every test: a suite must
never write into the source tree, and the retention sweep deletes files.
"""

import csv
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.utils import timezone

from apps.audit import exports
from apps.audit.models import AuditLog
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.export_helpers import exported_file
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")


@pytest.fixture()
def wired(tmp_path, settings):
    """The deployment's own wiring — real store, real transport, eager — with
    the artifacts directory pointed at tmp_path."""
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


def write_row(
    tenant, *, action, entity_type="invoice", entity_id=None, actor=None, before=None, after=None
):
    return AuditLog.objects.create(
        tenant_id=tenant.id,
        actor_user_id=getattr(actor, "id", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id or uuid.uuid4(),
        before=before,
        after=after,
    )


def seed_trail(idn, users):
    """Three rows: a money action, a system job's row, and a masked correction."""
    return {
        "issued": write_row(
            idn.silvercreek,
            action="invoice.issued",
            actor=users.alex,
            after={"total": "142.50", "status": "issued"},
        ),
        "system": write_row(
            idn.silvercreek, action="billing.run_completed", entity_type="bill_run"
        ),
        "masked": write_row(
            idn.silvercreek,
            action="account.updated",
            entity_type="account",
            actor=users.priya,
            before={"dob": "06/****"},
            after={"dob": "11/****"},
        ),
    }


def export_as(client, query=""):
    response = api_post(client, f"/audit-log/export{query}")
    assert response.status_code == 202, response.content
    return response.json()


def read_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def artifact_of(job_id):
    """The job row + the file on disk.

    `result_link` is the IS-11 DOWNLOAD ROUTE (the download lane, 2026-08-10);
    the filesystem path the job body wrote lives on the record's payload, which
    is where operators — and this helper — read it from.
    """
    row = tenancy_models.Job.objects.get(id=job_id)
    assert row.result_link == f"/api/exports/{row.id}/file", row.result_link
    return row, exported_file(row.id)


# ── TC-1 — the file itself (IS-9/IS-11) ─────────────────────────────────────
def test_us_aud_006_tc1__the_export_job_writes_the_is9_csv(idn, wired):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client(*ALEX)

    body = export_as(alex, "?f.action=invoice.issued")
    job, path = artifact_of(body["job_id"])

    assert job.status == core_jobs.SUCCEEDED  # the 202 actually finished
    assert job.progress == {"done": 1, "total": 1}
    assert job.error is None
    # PO 2026-10-02: the file is in S3 under the utility's export folder, not
    # in a directory — `exported_file` reads it back through its row.
    assert path.exists()
    from tests.export_helpers import exported_row

    assert exported_row(body["job_id"]).storage_key.startswith("t/silvercreek/export/")

    rows = read_csv(path)
    # Exactly ONE header row, stable snake_case columns, no metadata rows.
    assert rows[0] == list(exports.EXPORT_COLUMNS)
    assert rows[0] == ["when", "actor", "action", "entity_type", "entity_id", "summary", "source"]
    assert len(rows) == 2  # header + the one filtered row
    when, actor, action, entity_type, entity_id, summary, source = rows[1]
    assert actor == "Alex Reed" and action == "invoice.issued"
    assert entity_type == "invoice" and uuid.UUID(entity_id)
    assert "total" in summary
    assert source == ""  # GAP AUD-D2 — column present, honest-empty
    assert when.startswith(timezone.now().strftime("%Y-%m-%d"))

    # {tenant}_{report}_{period}_{basis}_{generated}.csv, basis `event-time`.
    tenant_part, report, period, basis, generated = path.stem.split("_")
    assert (tenant_part, report, basis) == ("silvercreek", "audit-log", "event-time")
    assert period == "hot-window"  # no explicit range: the window it covered
    assert len(generated) == len("20260809T1655")
    assert path.suffix == ".csv"


def test_us_aud_006_tc1_period__an_explicit_month_range_names_the_month(idn, wired):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client(*ALEX)
    today = timezone.now().date()
    month = today.strftime("%Y-%m")
    body = export_as(alex, f"?f.from={month}-01&f.to={month}-28")
    _, path = artifact_of(body["job_id"])
    assert path.stem.split("_")[2] == month  # US-AUD-006 TC-1's `2026-08` segment


def test_us_aud_006_tc1_utf8__the_file_is_utf8_with_the_stored_masked_values(idn, wired):
    """BR-AUD-006: the export renders what is stored — masking included, and
    non-ASCII survives the round trip (IS-9: UTF-8)."""
    users = idn.seed_silvercreek()
    write_row(
        idn.silvercreek,
        action="account.updated",
        entity_type="account",
        actor=users.priya,
        before={"name": "José Ruíz", "dob": "06/****"},
        after={"name": "José Ruíz", "dob": "11/****"},
    )
    alex = signed_in_client(*ALEX)
    body = export_as(alex, "?f.action=account.updated")
    _, path = artifact_of(body["job_id"])
    text = path.read_text(encoding="utf-8")
    assert "06/**** → 11/****" in text
    assert "José" not in text  # unchanged fields are not "changed" (summarize)
    rows = read_csv(path)
    assert rows[1][5].startswith("dob: 06/****")


def test_us_aud_006_tc1_money_dates__is9_value_formatting(idn, wired):
    """IS-9 money/date rules, asserted on the formatters the writer uses.

    No audit COLUMN is money-typed (money-shaped values live inside
    before/after, which BR-AUD-006 forbids reformatting), so the rules are
    proved here on the helpers themselves rather than faked into a column.
    """
    assert exports.format_money(Decimal("142.5")) == "142.50"  # plain 2dp
    assert exports.format_money(Decimal("1234567.891")) == "1234567.89"  # no separators
    assert exports.format_money(Decimal("-0.005")) == "-0.01"  # half-up, display only
    assert exports.format_money(None) == ""

    tz = exports.tenant_timezone(uuid.uuid4())  # unset tenant → UTC, never guessed
    stamp = exports.format_when(
        timezone.now().replace(year=2026, month=8, day=9, hour=16, minute=55), tz
    )
    assert stamp.startswith("2026-08-09T16:55")
    assert stamp.endswith("+00:00")  # ISO 8601 WITH the offset


def test_us_aud_006_tc1_timezone__timestamps_render_in_the_tenants_zone(idn, wired):
    """IS-8/IS-9: the When column is the tenant's Regional timezone, not UTC."""
    users = idn.seed_silvercreek()
    tenancy_models.TenantSettings.objects.create(tenant=idn.silvercreek, timezone="America/Chicago")
    seed_trail(idn, users)
    alex = signed_in_client(*ALEX)
    body = export_as(alex, "?f.action=invoice.issued")
    _, path = artifact_of(body["job_id"])
    when = read_csv(path)[1][0]
    assert when.endswith("-05:00") or when.endswith("-06:00")  # CDT / CST, with offset


def test_us_aud_006_tc1_system_actor__a_null_actor_exports_as_system(idn, wired):
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client(*ALEX)
    body = export_as(alex, "?f.action=billing.run_completed")
    _, path = artifact_of(body["job_id"])
    assert read_csv(path)[1][1] == "system"  # BR-AUD-003


# ── the guards the job body inherits ────────────────────────────────────────
def test_us_aud_006_tc5__the_50k_cap_still_refuses_before_any_file_exists(idn, wired, monkeypatch):
    """BR-AUD-014: the cap is measured at ACCEPT time, so an oversize request
    produces no job and no partial file. Lowering the constant beats seeding
    50,000 rows — the guard under test is the refusal, not insert throughput."""
    from apps.audit import services as audit_services

    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    monkeypatch.setattr(audit_services, "EXPORT_ROW_CAP", 2)
    alex = signed_in_client(*ALEX)

    refused = api_post(alex, "/audit-log/export")
    assert refused.status_code == 422
    assert refused.json()["code"] == "BIZ-CAP"
    assert tenancy_models.Job.objects.count() == 0
    assert list(wired.glob("*.csv")) == []


def test_us_aud_006_tc8__the_file_holds_only_the_callers_own_tenant(idn, wired):
    """BR-AUD-007/BR-SHL-016: the job runs under the record's tenant context, so
    the query behind the file is that tenant's — zero foreign rows, ever."""
    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    jordan, _ = idn.seed_bluemesa_admin()
    write_row(idn.bluemesa, action="invoice.issued", actor=jordan)

    okafor = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    response = api_post(okafor, "/audit-log/export", tenant=BM)
    assert response.status_code == 202
    job, path = artifact_of(response.json()["job_id"])

    rows = read_csv(path)
    assert job.tenant_id == idn.bluemesa.id
    assert len(rows) == 2  # header + Blue Mesa's single row
    assert rows[1][1] == "Jordan Ellis"
    assert path.stem.startswith("bluemesa_")


def test_us_aud_006_br018__an_export_no_longer_sweeps_on_the_way_in(idn, wired):
    """BR-REP-018/IS-11: generated files are retained `file_retention_days`.
    ⚠ **SINCE 2026-10-02 THE SWEEP DOES NOT RIDE AN EXPORT** (PO: *"Once a day,
    for each utility, the system deletes exports older than that utility's own
    setting"*) — the daily per-utility sweep does (tests/test_s3a_export_store.py).
    An older audit export past retention is left for it, still `stored`."""
    from apps.tenancy.export_models import JobArtifact

    users = idn.seed_silvercreek()
    seed_trail(idn, users)
    alex = signed_in_client(*ALEX)
    first = export_as(alex, "?f.action=invoice.issued")
    JobArtifact.objects.filter(job_id=first["job_id"]).update(
        created_at=timezone.now() - timedelta(days=exports.ARTIFACT_RETENTION_DAYS + 1)
    )
    second = export_as(alex, "?f.action=invoice.issued")
    _, path = artifact_of(second["job_id"])
    assert JobArtifact.objects.get(job_id=first["job_id"]).status == "stored"
    assert path.exists()


def test_us_aud_006_br014__a_writer_failure_lands_on_the_job_not_the_caller(
    idn, wired, monkeypatch
):
    """The accept already answered 202: a broken writer must show up as a
    FAILED job with its error, never as a 500 on the export request."""
    users = idn.seed_silvercreek()
    seed_trail(idn, users)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(exports, "scratch_dir", broken)
    alex = signed_in_client(*ALEX)
    body = export_as(alex, "?f.action=invoice.issued")  # still 202
    job, _unused = tenancy_models.Job.objects.get(id=body["job_id"]), None
    assert job.status == core_jobs.FAILED
    assert job.error == "OSError: disk full"
    assert job.result_link is None
    # BR-AUD-014's self-audit row was still written: the export WAS requested.
    assert len(idn.rows_for("audit.exported")) == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-006@009e809 (EP-AUD-02 export story — hash = sha256/7 of the source epic)
# generated: 2026-08-10 by story-coder v1 (job-runner lane — TC-1's file, unbuildable until a job store existed) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S61 is a later lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_aud_006_export_job.py✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: TC-1's row count (1,131 money rows) and its literal filename are the epic's Brazos Bend fixture; these TCs assert the CONTRACT (columns, one header, offsets, filename grammar) against the identity lane's Silver Creek fixture, which is the tenant this suite can sign into — recorded, not silently substituted · the RLS half of TC-8 stays with the G5 isolation suite (sqlite cannot enforce RLS); the app-filter half is asserted here · no download-endpoint TC exists because no download endpoint exists (IS-11, reports W5) — the artifact path is asserted instead · [path-tenancy lane 2026-08-10] result_link is `/api/exports/{id}/file`; requests name their tenant instead of a Host
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
