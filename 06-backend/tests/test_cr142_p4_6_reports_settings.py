# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, task `P4.6` (*"Settings →
#          Configure → Reference data → Reports: retention and the default
#          format"*) and `P5.12` (the door that reaches it). Drawing p047
#          legend ④, p048's TODAY/TASK rows and p049's consequence block,
#          read as IMAGES per B14 rule 42.
# Rules:   BR-REP-018 CONFIRMED (PO 2026-08-08, IS-11 — *"retained 3 days by
#          default, tenant-configurable"*) · BR-TEN-024 (atomic per-tab save,
#          one audit row) · BR-TEN-043 (event-time forward) · NFR-5 (no hard
#          caps) · B2 §2 (no module writes another module's row) ·
#          CLAUDE.md rule 1 (tenant scoping) · rule 7 (audited) ·
#          hard-won law 2 and its mirror · law 7.
# ───────────────────────────────────────────────────────
"""Retention and the default format, asserted as BEHAVIOUR rather than storage.

⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY — asked before they were
written, per hard-won law 7 habit (2).**

  · **Asserting the stored document** would pass over a product that saved the
    number and went on sweeping at three days — which is precisely the state
    `BR-REP-018` was in for fifty days, with the rule signed and the storage
    absent. So the retention cases assert what the NUMBER DOES: what
    `export_store.sweep_tenant` deletes, and what screen `5·1` presents.
  · **Asserting `artifact_retention_days()` returns 7** would pass over a
    reader that ignored the tenant and happened to be called under a tenant
    whose setting was the platform default. So two tenants are set to
    different numbers in one test and both are read.
  · **Asserting the sweep removed a file** would pass over a sweep that
    removed EVERY tenant's file — the exact damage a per-tenant retention
    makes possible in a shared directory. So the sibling tenant's file is
    asserted to SURVIVE in the same case.
  · **Asserting a 200 from `PUT /settings/reports`** would pass over an
    endpoint that accepted zero days, which is not a shorter window but *every
    download link in the product is broken*. The refusal is asserted by name.
  · **`pytest.skip` is not used anywhere in this file.** A skip reads as a
    pass in the summary line.

⚠ **NOTHING HERE ASSERTS A PDF.** `apps.reports.models.FORMATS` is `("csv",)`
because no PDF renderer is declared anywhere in this product. The format case
asserts that a second value is REFUSED, which is the honest shape of a choice
set with one member.
"""

from pathlib import Path

import pytest

from apps.reports import run_history, schedules_api
from apps.reports.models import ReportDefinition
from apps.tenancy import exports, models as tenancy_models, selectors, services
from apps.tenancy.settings_families import REPORTS
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import seeding_ctx, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db


def _settings_row(tenant):
    with seeding_ctx(tenant):
        row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant_id=tenant.id)
    return row


def _set_retention(tenant, days):
    row = _settings_row(tenant)
    with seeding_ctx(tenant):
        row.reports = {**(row.reports or {}), "file_retention_days": days}
        row.save(update_fields=["reports", "updated_at"])


# ── The default is the constant, which is where every tenant is today ──────


def test_a_tenant_that_has_set_nothing_is_where_it_always_was(brazos):
    """`BR-REP-018`'s three days, unchanged, with no row and with a seeded one."""
    with tenant_ctx(brazos):
        assert exports.artifact_retention_days() == exports.ARTIFACT_RETENTION_DAYS == 3
    _settings_row(brazos)
    with tenant_ctx(brazos):
        assert exports.artifact_retention_days() == 3
        assert exports.default_download_format() == "csv"


def test_outside_a_tenant_it_answers_the_platform_default_and_never_raises():
    """The sweep runs before a job resolves its tenant; a screen never falls
    over a number whose safe answer is already known."""
    assert exports.artifact_retention_days() == 3
    assert exports.default_download_format() == "csv"


# ── Two tenants, two numbers, one directory ────────────────────────────────


def test_two_tenants_read_their_own_number_and_neither_reads_the_others(brazos, lonestar):
    _set_retention(brazos, 7)
    _set_retention(lonestar, 1)
    with tenant_ctx(brazos):
        assert exports.artifact_retention_days() == 7
    with tenant_ctx(lonestar):
        assert exports.artifact_retention_days() == 1
    # And named explicitly, which is what `run_list_export_job` does.
    assert exports.artifact_retention_days(brazos.id) == 7
    assert exports.artifact_retention_days(lonestar.id) == 1


def test_a_short_window_sweeps_only_its_own_tenants_files(tmp_path, brazos, lonestar, export_bucket):
    """⚠ THE CASE THIS WHOLE FEATURE COULD HAVE BROKEN.

    Every utility's export files share ONE bucket (PO 2026-10-02 — exports in
    S3, at `t/<web name>/export/…`). The moment retention became a per-tenant
    number, an unscoped sweep at one utility's one-day setting would have
    deleted another utility's two-day-old file.
    """
    import datetime as dt

    from django.utils import timezone

    from apps.tenancy import export_store
    from apps.tenancy import models as tenancy_models
    from apps.tenancy.export_models import JobArtifact

    def two_day_old(tenant):
        source = Path(tmp_path) / f"{tenant.subdomain}_ar-aging_2026-09.csv"
        source.write_text("code,name\n", encoding="utf-8")
        with tenant_ctx(tenant):
            job = tenancy_models.Job.objects.create(tenant=tenant, kind="list_export", status="succeeded")
            row = export_store.publish(
                job_id=job.id,
                tenant_id=tenant.id,
                path=source,
                display_name=source.name,
                content_type="text/csv",
            )
            JobArtifact.objects.filter(id=row.id).update(
                created_at=timezone.now() - dt.timedelta(days=2)
            )
        return row

    mine, theirs = two_day_old(brazos), two_day_old(lonestar)
    _set_retention(brazos, 1)
    _set_retention(lonestar, 7)
    # DEF-TEN-9146: the sweep takes the UTILITY, never a prefix and a window.
    with tenant_ctx(brazos):
        result = export_store.sweep_tenant(brazos.id)
    assert result.deleted == 1
    assert JobArtifact.objects.get(id=mine.id).status == "deleted"
    assert JobArtifact.objects.get(id=theirs.id).status == "stored"
    export_bucket.head_object(Bucket="sbh-test-bucket", Key=theirs.storage_key)  # still there


# ── The endpoint: what it accepts, what it refuses, what it audits ─────────


def test_the_family_saves_one_key_and_leaves_the_other_alone(brazos, audit_rows):
    actor = staff_actor(brazos)
    with tenant_ctx(brazos):
        before = selectors.settings_family("reports")
        assert before == {"file_retention_days": 3, "default_download_format": "csv"}
        after = services.save_settings_family(actor, "reports", {"file_retention_days": 14})
    assert after == {"file_retention_days": 14, "default_download_format": "csv"}
    assert any(row.get("action") == REPORTS.audit_action for row in audit_rows)


def test_zero_days_is_refused_by_name(brazos):
    """Not a shorter window — *every download link in the product is broken*."""
    actor = staff_actor(brazos)
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.save_settings_family(actor, "reports", {"file_retention_days": 0})
    assert "file_retention_days" in str(caught.value.field_errors)


def test_there_is_no_maximum_because_nfr_5_forbids_one(brazos):
    actor = staff_actor(brazos)
    with tenant_ctx(brazos):
        saved = services.save_settings_family(actor, "reports", {"file_retention_days": 3650})
    assert saved["file_retention_days"] == 3650


def test_a_format_the_product_cannot_produce_is_refused(brazos):
    actor = staff_actor(brazos)
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            services.save_settings_family(actor, "reports", {"default_download_format": "pdf"})


# ── What the number DOES, which is the half a stored value cannot prove ────


def test_screen_5_1_states_this_utilitys_own_number(brazos):
    """`P5.12` — the retention line was `3` in eleven catalogues over a server
    that had already made retention settable."""
    _set_retention(brazos, 9)
    with tenant_ctx(brazos):
        page = run_history.runs(q="", resource=None, status=None, page=1, per=5)
    assert page["retention_days"] == 9


def test_a_schedule_created_without_a_format_takes_the_tenants_default(brazos):
    """The *Default format* card does something, rather than being stored."""
    with tenant_ctx(brazos):
        assert schedules_api._format_or_tenant_default(None) == "csv"
        assert schedules_api._format_or_tenant_default("csv") == "csv"


def test_the_reports_family_is_registered_and_owns_exactly_two_parameters():
    """A third parameter arriving without a card is hard-won law 2's shape."""
    assert REPORTS.slug == "reports"
    assert [p.key for p in REPORTS.params] == [
        "file_retention_days",
        "default_download_format",
    ]


def test_reports_never_writes_the_tenancy_row(brazos):
    """B2 §2 — the CARD is drawn under a Reports heading and the WRITE is
    tenancy's. Asserted as an absence of a writer, not as a comment."""
    import subprocess

    hits = subprocess.run(
        ["grep", "-rn", "TenantSettings", "apps/reports/"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert hits == "", f"apps/reports touches tenancy's settings row: {hits}"


def test_the_definition_table_is_untouched_by_this_change(brazos):
    """A guard against the obvious wrong home: a `retention` column on a
    report definition would be a second answer per report."""
    assert not any(f.name == "retention_days" for f in ReportDefinition._meta.get_fields())
