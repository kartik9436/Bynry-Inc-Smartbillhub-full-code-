# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-001 (EP-AUD-01 — the platform audit-write contract) — the STORE half ·
#           US-AUD-006 (EP-AUD-02 — S61 CSV export: 50k cap, 202 + job_id, and the
#           export's OWN audit row) · US-AUD-007 (EP-AUD-03 — the retention job's
#           run recorder + the self-audit rows it writes per affected tenant)
#           Screens: S61
# Rules:    BR-AUD-001 (every money action writes a row) · BR-AUD-002 (append-only —
#           no update/delete API exists) · BR-AUD-003 (standard row shape) ·
#           BR-AUD-007 (tenant from context, never a parameter) · BR-AUD-008 (one
#           lightweight INSERT, never a cascade) · BR-AUD-015 (no FK on tenant_id) ·
#           BR-AUD-009 (who may read/export S61: System Admin + Executive) ·
#           BR-AUD-013 (the export measures the SAME bounded query the list serves) ·
#           BR-AUD-012 (2 yr hot → cold, 7 yr total, AUTOMATIC, audited — the run
#           record + the per-tenant self-audit rows land here) ·
#           BR-AUD-014 (CSV under BR-SHL-016 guards: 50,000-row cap → 422 BIZ-CAP;
#           every audit export writes its own audit row) · HR-7
# Tests:    06-backend/tests/test_us_aud_001_store.py (store half) ·
#           06-backend/tests/test_us_aud_004_006_viewer.py (export accept half, per-TC) ·
#           06-backend/tests/test_us_aud_006_export_job.py (the job body, per-TC)
# ───────────────────────────────────────────────────────
"""audit service layer — the ONLY write path into this module's tables (B1 boundary rule).

`core.audit` assembles rows and hands them to a registered sink; this module IS that
sink. The split keeps `core` free of app-model imports while leaving exactly one place
that inserts into `audit_log`.

There is deliberately no update, delete, or bulk-edit function here: the trail is
append-only (BR-AUD-002), backed by the table's own trigger. `request_export` is not
an exception — it INSERTs its own `audit.exported` row and mutates nothing.

Export mechanics, stated rather than assumed:
- The cap is measured on the rows the caller's CURRENT filters select, inside the
  same bounded query the list serves (BR-AUD-013), so "narrow your filters" is
  advice the number actually supports.
- The file itself is produced by the BE-07 job (202 + job_id, poll /jobs/{id}).
  The IS-9/IS-11 CSV writer lives in apps/audit/exports.py and is registered as
  this kind's job body by `register()` below; apps.tenancy registers the store
  behind the record (it hosts the `jobs` table). Both halves landed 2026-08-10
  — before that, enqueue failed LOUDLY rather than answering a 202 that
  promised a poll URL with no record behind it.
"""

from typing import Any

from apps.tenancy import exports as tenancy_exports
from core import archival as archival_kernel
from core import audit as audit_kernel
from core import errors
from core import jobs as core_jobs
from core import tenancy as tenancy_kernel
from core.permissions import EXECUTIVE, SYSTEM_ADMIN, require_role

from . import exports, selectors
from .models import ArchiveJobRun, AuditLog

# BR-AUD-014 / BR-SHL-016 / 11b G11: the export guard, one grep away.
EXPORT_ROW_CAP = 50_000
EXPORT_JOB = "audit_export"


def store_row(row: dict[str, Any]) -> None:
    """Persist one assembled audit row — the sink `core.audit` calls (BR-AUD-008).

    The kernel has already resolved the tenant from context and refused the write if
    it was absent (BR-AUD-007), so this is a single INSERT and nothing else: no
    signals, no derived writes, no read-back. `created_at` is stamped by the store.

    US-AUD-010 adds the three actor columns. They arrive already validated — the
    kernel refuses a named actor that also carries a user id (BR-RBS-015) and an
    AutomationActor refuses an unknown kind or an empty name at construction — so
    nothing is re-checked here. `.get()` with a default rather than `[...]`
    because a caller assembling a row dict by hand (the export replay, a test)
    predates these keys and must keep writing a lawful unnamed row.
    """
    AuditLog.objects.create(
        tenant_id=row["tenant_id"],
        actor_user_id=row.get("actor_user_id"),
        actor_kind=row.get("actor_kind"),
        actor_label=row.get("actor_label"),
        actor_version=row.get("actor_version"),
        action=row["action"],
        entity_type=row["entity_type"],
        entity_id=row.get("entity_id"),
        before=row.get("before"),
        after=row.get("after"),
    )


@require_role(SYSTEM_ADMIN, EXECUTIVE, br_ref="BR-AUD-009")
def request_export(
    *,
    actor: Any,
    tenant_id: Any,
    filters: dict[str, str] | None = None,
    archive: bool = False,
) -> dict[str, Any]:
    """US-AUD-006: accept an S61 CSV export, or refuse it at the 50k cap.

    Order matters and is the rule's own: COUNT first (BR-AUD-014 — an oversize
    request produces no partial file and no job), then enqueue, then write the
    export's own audit row (BR-AUD-014's self-audit clause; audit payloads
    contain money actions, so BR-SHL-016's money-export audit applies a
    fortiori).

    Roles: System Admin + Executive — the S61 read roles (BR-AUD-009). A4 names
    no audit-log row at all; the disposition is recorded in api.py.

    Returns the BE-07 202 body: {job_id, status_url}.
    """
    row_count = selectors.audit_result_set(tenant_id, filters=filters, archive=archive).count()
    if row_count > EXPORT_ROW_CAP:
        # 422 BIZ-CAP (11b G11) — "Narrow your filters to export."
        raise errors.BizError(
            errors.BIZ_CAP,
            br_ref="BR-AUD-014",
            message_key="audit.export.row_cap_exceeded",
            params={"rows": row_count, "cap": EXPORT_ROW_CAP},
        )
    record = core_jobs.enqueue(
        EXPORT_JOB,
        payload={
            "filters": dict(filters or {}),
            "archive": bool(archive),
            "row_count": row_count,
            "actor_user_id": str(getattr(actor, "id", None) or getattr(actor, "pk", "")) or None,
        },
    )
    audit_kernel.money_action(
        actor,
        "audit.exported",
        "audit_log",
        None,  # the export covers a FILTERED SET, not one row (BR-AUD-003 entity)
        after={
            "filters": dict(filters or {}),
            "archive": bool(archive),
            "row_count": row_count,
            "job_id": record["id"],
        },
    )
    return core_jobs.accepted(record)


# ── US-AUD-009: the A14 Compliance card "User activity audit" feed ──────────
#: The S44 card routes HERE, not to the generic viewer (BR-AUD-017; the reports
#: pack's R-2 flag is DEDUPED for this one card). The key is the IS-11 report
#: slug from US-AUD-009 §4's own filename fixture
#: (`brazosbend_user-activity-audit_2026-07_event-time_20260809T1710.csv`),
#: derived from a signed fixture rather than invented — the same derivation
#: apps/reports/api.py records for its two keys.
FEED_KEY = "user_activity_audit"
FEED_SLUG = "user-activity-audit"

#: The feed rides the SAME BE-07 job kind as the S61 export, with its own report
#: slug on the payload. Deliberately not a second kind: a job kind is a platform
#: registration (it becomes a downloadable-export kind), and the two produce the
#: same bytes through the same writer under the same guards — only the
#: filename's `{report}` segment differs. A second kind would have widened the
#: platform's download surface for a difference of one string.
FEED_JOB = EXPORT_JOB

#: BR-AUD-017: the S61 dataset and NOTHING beyond it. Columns outside this set
#: stay unratified (the reports R-2 candidate), so the feed refuses them by name
#: rather than quietly serving something A1 S61 never ratified.
FEED_COLUMNS: tuple[str, ...] = ("when", "actor", "action", "entity", "summary", "source")


def feed_definition() -> dict[str, Any]:
    """What the S44 catalog needs to route the card here (US-REP-001 consumes).

    PUBLISHED for the reports module to resolve by name — reports renders the
    card, audit owns the dataset (pack assignment 2026-08-09). Everything in it
    is quoted from ratified law: the six S61 columns (A1 S61 addendum), S61's
    filter vocabulary as the report parameters (BR-AUD-009), the `event-time`
    date basis (no money basis applies) and the BR-SHL-016 row cap.

    **PDF is declared UNAVAILABLE, not omitted.** US-AUD-009 §1 asks for CSV
    *and* a compliance-class PDF (letterhead, period, filters echoed,
    generated-at + by whom, page X/Y). This deployment has no PDF renderer at
    all — not in this module, not in reports, not in core — so the definition
    says `pdf: false` with the reason, and the day a renderer lands the card
    gains the format without a story rewrite. Answering with a CSV renamed
    `.pdf`, or a 202 for a file nobody can produce, is the failure this field
    exists to avoid (hard-won law 1).
    """
    return {
        "key": FEED_KEY,
        "slug": FEED_SLUG,
        "owner": "audit",
        "card": "compliance.user_activity_audit",  # A14 §Report library
        "columns": list(FEED_COLUMNS),
        "parameters": list(selectors.AUDIT_FILTERS),  # S61's own filter vocabulary
        "date_basis": "event-time",
        "row_cap": EXPORT_ROW_CAP,
        "formats": {
            "csv": True,
            "pdf": False,
        },
        "pdf_unavailable_reason": (
            "no PDF renderer exists on this deployment (no module in this "
            "codebase produces one); the IS-11 compliance-PDF half of "
            "US-AUD-009 is REPORTED, not stubbed"
        ),
        "column_extensions": "unratified — beyond the A1 S61 set (reports R-2)",
    }


@require_role(SYSTEM_ADMIN, EXECUTIVE, br_ref="BR-AUD-009")
def request_feed(
    *,
    actor: Any,
    tenant_id: Any,
    filters: dict[str, str] | None = None,
    columns: list[str] | None = None,
    fmt: str = "csv",
) -> dict[str, Any]:
    """US-AUD-009: run the "User activity audit" feed over the S61 dataset.

    The SAME guarded pipeline as the S61 export (BR-AUD-014/BR-SHL-016): the
    50k cap is measured on the caller's own filters before any file exists, the
    generation writes its own audit row, and the file is produced by the BE-07
    job. What differs is the report identity — the filename's `{report}` segment
    is `user-activity-audit`, which is what makes the compliance evidence file
    recognisable as itself (US-AUD-009 TC-2).

    Two refusals, both stated in the story:
      · TC-5 — a bespoke column ("login duration") is NOT available. Beyond the
        ratified S61 set nothing is invented; the refusal names R-2.
      · a PDF request is refused with the renderer's absence as the reason
        (see `feed_definition`), never a CSV wearing a .pdf name.
    """
    requested = [str(column) for column in (columns or FEED_COLUMNS)]
    unsupported = [column for column in requested if column not in FEED_COLUMNS]
    if unsupported:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="audit.feed.column_unratified",
            params={
                "columns": unsupported,
                "available": list(FEED_COLUMNS),
                "reference": "R-2",
            },
        )
    if fmt != "csv":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-AUD-017",
            message_key="audit.feed.format_unavailable",
            params={"format": fmt, "reason": feed_definition()["pdf_unavailable_reason"]},
        )
    row_count = selectors.audit_result_set(tenant_id, filters=filters).count()
    if row_count > EXPORT_ROW_CAP:
        raise errors.BizError(  # TC-6: "Narrow your filters"
            errors.BIZ_CAP,
            br_ref="BR-AUD-014",
            message_key="audit.export.row_cap_exceeded",
            params={"rows": row_count, "cap": EXPORT_ROW_CAP},
        )
    record = core_jobs.enqueue(
        FEED_JOB,
        payload={
            "filters": dict(filters or {}),
            "archive": False,  # the feed reads HOT; archive ranges go via US-AUD-008
            "row_count": row_count,
            "report_slug": FEED_SLUG,
            "actor_user_id": str(getattr(actor, "id", None) or getattr(actor, "pk", "")) or None,
        },
    )
    audit_kernel.money_action(
        actor,
        "report.exported",
        "audit_log",
        None,
        after={
            "report": FEED_KEY,
            "filters": dict(filters or {}),
            "row_count": row_count,
            "job_id": record["id"],
            "date_basis": "event-time",
        },
    )
    return core_jobs.accepted(record)


# ── US-AUD-007 / US-MET-020: the retention job's two sinks ──────────────────
def record_archive_run(run: dict[str, Any]) -> Any:
    """Append one `archive_job_runs` row (BR-AUD-012 "audited"; BR-MET-055).

    A PLATFORM record, not a tenant one — see the model docstring for why a
    month-partitioned table's archival belongs to no tenant. INSERT only: there
    is no update or delete function for this table anywhere.
    """
    return ArchiveJobRun.objects.create(
        table_name=run["table"],
        run_date=run["run_date"],
        hot_window_months=run["hot_window_months"],
        retention_months=run["retention_months"],
        archived=run["archived"],
        purged=run["purged"],
        status=run["status"],
        note=run.get("note"),
    )


def write_archive_audit(table: str, action: str, partition: str, payload: dict[str, Any]) -> None:
    """The self-audit half: the job records its own actions in the trail.

    ONE ROW PER AFFECTED TENANT, under that tenant's own context. That is not a
    convenience — `audit_log.tenant_id` is NOT NULL and every read of it is
    RLS-scoped (BR-AUD-007), so a platform-wide row would have no tenant to
    belong to and no staff member who could ever see it. Each tenant sees the
    archival of the partition holding ITS rows and learns nothing about anyone
    else's: the payload carries partition name, row count and digest only.

    `actor` is None — BR-AUD-003: a null actor means a system job, and the job
    names itself in the payload. Which is also US-MET-020 TC-4 / US-AUD-007 TC-4
    made visible in the trail: there is no human actor because there is no
    manual path.
    """
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:  # a partition with no rows audits nothing
        return
    # `tenant_context` CLEARS on exit rather than restoring what was there
    # before (core/tenancy.py — a job's normal shape is to have no ambient
    # context, and clearing is the safe default there). This writer runs once
    # PER TENANT inside one job, and it must not leave the process without the
    # context its caller had: found the hard way when the S25 archive test's
    # next query raised AUTH-003 with nothing wrong in it. Saved and restored
    # here rather than by changing the 🔒 kernel's contract for one caller.
    previous = tenancy_kernel.current_tenant_id()
    with tenancy_kernel.tenant_context(tenant_id):
        audit_kernel.money_action(
            None,
            action,
            table,
            None,  # the subject is a PARTITION, not a row of the table (BR-AUD-003)
            after={
                "job": "archive_partitions",
                "partition": partition,
                **{key: value for key, value in payload.items() if key != "tenant_id"},
            },
        )
    if previous is not None:
        tenancy_kernel.set_current_tenant(previous)


def register() -> None:
    """Wire this module into the kernels. Called once from AuditConfig.ready().

    Three registrations, all the same shape (core never imports app code): the
    audit SINK (BE-03), the export JOB BODY (BE-07), and this module's export
    KIND with the IS-11 download route — the module that owns the work
    registers the callable that does it and declares that its output is a file
    a user may fetch. GET /exports/{job_id}/file therefore serves S61's CSV
    without the platform ever hardcoding the string "audit_export".
    """
    audit_kernel.set_audit_sink(store_row)
    core_jobs.set_job_handler(EXPORT_JOB, exports.run_export_job)
    tenancy_exports.register_export_kind(EXPORT_JOB)
    # US-AUD-009's feed rides the SAME kind (FEED_JOB == EXPORT_JOB) — see the
    # constant. Nothing extra to register.
    # US-AUD-007 / US-MET-020: this module hosts `archive_job_runs` and owns the
    # trail, so it registers both of the retention job's sinks. core.archival
    # therefore imports no app model, the same split core.jobs uses.
    archival_kernel.set_run_recorder(record_archive_run)
    archival_kernel.set_self_auditor(write_archive_audit)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@e6cc9c3 (EP-AUD-01 + audit 02-business-rules snapshot)
# packet: US-AUD-007@6b3d915 (EP-AUD-03 retention story — the run recorder + self-audit sinks, added 2026-08-15)
# packet: US-AUD-009@6b3d915 (EP-AUD-03 feed story — the A14 Compliance card's feed over the S61 dataset)
# packet: US-AUD-006@009e809 (EP-AUD-02 export story — hash = sha256/7 of the source epic; amended 2026-08-09 by the API-gap lane)
# generated: 2026-08-09 by Eng-Lead (W0 gap closure — the kernel's missing store half) · AMENDED 2026-08-09 by story-coder (API-gap lane: request_export) · AMENDED 2026-08-10 by story-coder (job-runner lane: the export job body is registered here)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S61 is a later lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [job-runner lane 2026-08-10] ruff✔ black✔ · pytest tests/test_us_aud_006_export_job.py✔ tests/test_us_aud_004_006_viewer.py✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · pytest tests/test_us_aud_001_store.py✔ · suite green · run_gates✔ · trace_lint✔ · [API-gap lane 2026-08-09] ruff✔(E4/E7/E9/F on the app files — the test tier carries the repo's pre-existing F811 fixture-import pattern) black✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: [US-AUD-007/009 lane 2026-08-15] the retention job's self-audit writes ONE row per affected tenant under that tenant's own context — a month-partitioned table's archival belongs to no single tenant and audit_log.tenant_id is NOT NULL, so a platform-wide row would have no tenant and no reader; the operator's record is the (tenant-less) archive_job_runs row · the US-AUD-009 compliance PDF is REFUSED, not stubbed (no PDF renderer exists anywhere in this codebase) — feed_definition() carries the reason and the day a renderer lands the card gains the format with no story rewrite · the feed's report key/slug are derived from US-AUD-009 §4's own filename fixture, the same derivation apps/reports/api.py records for its two keys, and rename with US-REP-001's catalog if it lands one · [job-runner lane 2026-08-10] the export JOB BODY now EXISTS (apps/audit/exports.py, registered below) and core.jobs has a live store (apps.tenancy) — the two absences this trailer recorded on 2026-08-09 are CLOSED; what remains open is the download endpoint for the produced file (IS-11, reports W5), so the job's result_link is a `file:` artifact reference — REPORTED in exports.py · the export audit row carries entity_id NULL: an export covers a filtered SET, not one row (BR-AUD-003 leaves entity_id nullable) — Eng disposition, flagged · export roles = the BR-AUD-009 read roles (System Admin + Executive); A4 names no audit-log row, disposition recorded in api.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
