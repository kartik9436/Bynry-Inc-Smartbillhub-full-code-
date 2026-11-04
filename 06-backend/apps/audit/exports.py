# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-006 (EP-AUD-02 — the S61 CSV export: the JOB BODY half; the
#           accept/cap/audit half lives in apps/audit/services.py)  Screens: S61
# Rules:    BR-AUD-014 (CSV per IS-9/IS-11 under BR-SHL-016 guards; 50k cap
#           measured at accept time; every export writes its own audit row) ·
#           BR-AUD-013 (the file covers the SAME bounded query the list serves) ·
#           BR-AUD-007 (tenant-scoped only — the job runs in the record's
#           tenant context, so RLS answers for the file too) · BR-AUD-006
#           (masked values are written exactly as stored — nothing unmasks) ·
#           BR-AUD-003 (null actor = system job) · BR-SHL-016 (server-side,
#           streamed, under the caller's tenant context) · BR-REP-018 (IS-11
#           download contract + 3-day retention of generated files)
# Tests:    06-backend/tests/test_us_aud_006_export_job.py (per-TC)
# Impacts:  core.jobs handler registry (registered by apps/audit/services.py
#           register(), called from AuditConfig.ready) · the S61 Export button
#           via GET /jobs/{id} result_link
# ───────────────────────────────────────────────────────
"""US-AUD-006 export JOB BODY — the IS-9/IS-11 CSV writer behind the 202.

`services.request_export` counts, caps, audits and enqueues; the file itself is
produced HERE, by the BE-07 runner, inside the job's own tenant context. Split
that way because the two halves fail differently: an oversize request must be
refused before any file exists (BR-AUD-014), while a writer crash must land on
the job record as `failed` and nowhere else.

The IS-9 CSV contract, implemented literally:
- UTF-8, comma-separated, exactly ONE header row, no metadata rows in the data.
- Stable snake_case columns, documented here as EXPORT_COLUMNS and nowhere else.
- Money: plain 2dp, no symbol, no thousands separator (`format_money`).
- Dates: ISO. Timestamps: the tenant's timezone WITH its offset (`format_when`).
- Context lives in the FILENAME: {tenant}_{report}_{period}_{basis}_{generated}.csv
  with basis `event-time` — S61 has no money basis to name (US-AUD-006 TC-1).

Streaming: rows are pulled with .iterator() and written one at a time, so a
50,000-row export never materializes a 50,000-row list. The HTTP half of
"server-streamed" (bytes flowing to a browser) belongs to a download endpoint
that does NOT exist yet — IS-11 downloads are the reports module's W5 story.
Until it lands the job writes an ARTIFACT FILE and the job's `result_link`
names it with a `file:` reference; a link to an HTTP route nobody built would
be the one thing worse than an honest path. REPORTED.

**Where the writer lives (amended 2026-08-10, list-export lane).** The IS-9
value formatters, the artifacts directory, the retention sweep, the filename
grammar and the streamed CSV writer moved to `apps/tenancy/exports.py` so the
generic `POST /exports` uses the SAME bytes instead of a second copy (LAW 0).
They are re-exported here under their original names, so this module's
contract, its behavior and its tests are unchanged — and the two cross-module
READS this file used to make (the tenant's subdomain for the filename, its
timezone for the When column) are now LOCAL reads inside the module that owns
those rows. What stays here is what is S61's alone: the column spec, the
`{period}` rule for an audit WINDOW, and the job body.
"""

import logging
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.audit import selectors
from apps.tenancy.exports import (
    ARTIFACT_RETENTION_DAYS,
    CHUNK,
    PROGRESS_EVERY,
    TWO_DP,
    finish_artifact,
    format_money,
    format_when,
    scratch_dir,
    tenant_slug,
    tenant_timezone,
    write_csv,
)

logger = logging.getLogger("smartbillhub.audit")

# Re-exported so `from apps.audit import exports; exports.format_money(...)`
# keeps working for every existing caller and test (see the module docstring).
__all__ = [
    "ARTIFACT_RETENTION_DAYS",
    "BASIS_SEGMENT",
    "CHUNK",
    "EXPORT_COLUMNS",
    "PROGRESS_EVERY",
    "REPORT_SLUG",
    "TWO_DP",
    "artifact_filename",
    "finish_artifact",
    "format_money",
    "format_when",
    "period_segment",
    "run_export_job",
    "tenant_slug",
    "tenant_timezone",
    "write_csv",
]

# IS-9: "stable snake_case columns documented per report" — this tuple IS that
# documentation. The S61 visible columns (BR-AUD-009: When · Actor · Action ·
# Entity · Summary · Source) with Entity spelled out as its two stored parts,
# because a CSV consumer needs the id in its own column.
EXPORT_COLUMNS: tuple[str, ...] = (
    "when",
    "actor",
    "action",
    "entity_type",
    "entity_id",
    "summary",
    "source",
)

REPORT_SLUG = "audit-log"  # the {report} filename segment
BASIS_SEGMENT = "event-time"  # {basis}: S61 carries no money basis (BR-REP-001)


def period_segment(filters: dict[str, str], *, archive: bool) -> str:
    """The {period} filename segment, derived from the caller's own range.

    An explicit range inside one month reads as that month (`2026-08`, the
    US-AUD-006 TC-1 example); any other explicit range names both ends; with no
    range the file covers the query's whole window, and says which one
    (BR-AUD-013 — hot by default, archive only on an explicit opt-in).
    """
    start = str(filters.get("from") or "")[:10]
    end = str(filters.get("to") or "")[:10]
    if start and end:
        return (
            start[:7]
            if start[:7] == end[:7]
            else f"{start.replace('-', '')}-{end.replace('-', '')}"
        )
    if start or end:
        single = start or end
        return single[:7]
    return "archive-window" if archive else "hot-window"


def artifact_filename(
    tenant_id: Any,
    filters: dict[str, str],
    *,
    archive: bool,
    now: datetime,
    tz: ZoneInfo,
    report_slug: str = REPORT_SLUG,
) -> str:
    """IS-9: `{tenant}_{report}_{period}_{basis}_{generated}.csv`.

    `report_slug` defaults to S61's own export. US-AUD-009's feed passes
    `user-activity-audit`, which is what makes its compliance evidence file
    recognisable as itself (US-AUD-009 TC-2's filename fixture) while riding the
    identical guarded, audited pipeline.
    """
    generated = now.astimezone(tz).strftime("%Y%m%dT%H%M")
    return (
        "_".join(
            (
                tenant_slug(tenant_id),
                report_slug,
                period_segment(filters, archive=archive),
                BASIS_SEGMENT,
                generated,
            )
        )
        + ".csv"
    )


# ── the job body (BE-07 runner contract: record -> result_link) ─────────────
def run_export_job(record: dict[str, Any]) -> str:
    """Write the S61 CSV for one accepted export and return its result link.

    Runs under the record's tenant context (core.jobs.run_job entered it), so
    the query this writes is the caller's own tenant's — BR-AUD-007/BR-SHL-016
    "under the caller's tenant context", enforced by RLS on Postgres and by the
    explicit tenant filter in selectors on every tier.

    The 50,000-row cap is NOT re-checked here: BR-AUD-014 measures it at accept
    time precisely so no partial file can exist, and `row_count` from the
    payload is that measurement (used as the progress total).
    """
    payload = record.get("payload") or {}
    filters = dict(payload.get("filters") or {})
    archive = bool(payload.get("archive"))
    tenant_id = record["tenant_id"]

    # The archive opt-in reads the cold partitions too (US-AUD-008); the hot
    # default is the plain queryset. `.iterator()` streams either way.
    queryset = (
        selectors.audit_result_set(tenant_id, filters=filters, archive=True)
        if archive
        else selectors.audit_queryset(tenant_id, filters=filters)
    )
    total = payload.get("row_count")

    tz = tenant_timezone(tenant_id)
    # PO 2026-10-02 (exports move to S3): the CSV is built in this job's own
    # SCRATCH folder and stored by `finish_artifact`; the folder is removed
    # when the `with` below closes. Old files are no longer swept on the way
    # in — the daily per-utility sweep does it (`DEF-TEN-9146`'s rule kept).
    scratch = scratch_dir()
    path = Path(scratch.name) / artifact_filename(
        tenant_id,
        filters,
        archive=archive,
        now=timezone.now(),
        tz=tz,
        report_slug=str(payload.get("report_slug") or REPORT_SLUG),
    )

    names: dict[str, str] = {}

    def actor_label(actor_id: Any) -> str:
        """Display name, the id when the user row is gone, `system` when null
        (BR-AUD-003). Memoized: one lookup per distinct actor, not per row."""
        if actor_id is None:
            return selectors.SYSTEM_ACTOR
        key = str(actor_id)
        if key not in names:
            names.update(selectors.actor_names(tenant_id, [actor_id]))
            names.setdefault(key, key)
        return names[key] or key

    def actor_cell(row: Any) -> str:
        """US-AUD-010 — the export is a CONSUMER of the actor and had to be
        found by grepping for one, not by waiting for a screen to look wrong.

        Without this branch a named runbook exports as the literal word
        `system`, so the CSV a clerk hands to a disputing customer is the blank
        actor again on the one surface that leaves the building
        (`DEF-CUS-3653`'s lesson: before changing what a value means, grep for
        who reads it — an absence is invisible to every check this repo has).

        The cell is `Returned payments v4`. It is deliberately NOT the sentence
        the screen draws: a CSV column is a stable machine contract (IS-9), it
        is not translated, and `v4` is a version marker rather than an English
        word — the screen composes "version 4" in the reader's own language
        from the two stored fields (B14 rule 35).
        """
        if row.actor_kind is None:
            return actor_label(row.actor_user_id)
        label = row.actor_label or ""
        return f"{label} v{row.actor_version}" if row.actor_version else label

    def cells() -> Iterator[tuple[list[str], Any]]:
        """One S61 row per audit row, streamed — never a materialized list."""
        rows = (
            queryset.iterator(chunk_size=CHUNK)
            if hasattr(queryset, "iterator")
            else iter(queryset[0:None])
        )
        for row in rows:
            yield [
                format_when(row.created_at, tz),
                actor_cell(row),
                row.action,
                row.entity_type,
                str(row.entity_id) if row.entity_id else "",
                # Masked payload values render exactly as stored (BR-AUD-006).
                selectors.summarize(row.before, row.after),
                "",  # source — GAP AUD-D2: no B2 column, honest-empty
            ], row

    with scratch:
        done = write_csv(
            path,
            EXPORT_COLUMNS,
            cells(),
            job_id=record["id"],
            total=total,
            # NFR-4 + TD-17: the checkpoint is the last row written, so a resumed
            # run can say where it got to.
            checkpoint_of=lambda row: str(row.id),
        )
        logger.info("audit export wrote %s row(s) to %s", done, path.name)
        # IS-11: the link is the shared DOWNLOAD ROUTE (GET /exports/{job_id}/file),
        # the same one the generic list export returns; the file itself is in
        # the utility's `export/` folder in S3, found through its row.
        return finish_artifact(record["id"], path, tenant_id=tenant_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-006@009e809 (EP-AUD-02 export story — hash = sha256/7 of the source epic)
# generated: 2026-08-10 by story-coder v1 (job-runner lane — the export body the API-gap lane could not build without a job store)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — this is a job body; its resource is GET /jobs/{id}) E=deferred(no-frontend-half — S61 is a later lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · ruff✔(E4/E7/E9/F) black✔ py_compile✔ · pytest tests/test_us_aud_006_export_job.py✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# generated: AMENDED 2026-08-10 by story-coder (list-export lane — the IS-9 writer moved to apps/tenancy/exports.py so POST /exports reuses it; behavior and tests unchanged)
# exceptions: no DOWNLOAD endpoint exists (IS-11 downloads are the reports W5 story), so `result_link` is a `file:` reference to the artifact on local disk rather than an HTTP route — REPORTED, not faked · the artifacts directory is local disk: no object store exists on this deployment (the same absence tenants.logo_bytes records) · BR-REP-018's 3-day retention is enforced by a best-effort sweep on each export because celery-beat scheduling is TD-17; its "tenant-configurable" half has no storage — REPORTED · the `source` column is written empty (GAP AUD-D2 — no B2 column anchors UI/API/job) · money formatting is implemented and tested per IS-9 but NO audit column is money-typed: money-shaped values live inside before/after and are rendered as stored (BR-AUD-006 forbids reformatting them) — stated so the absence is not read as an omission · [list-export lane 2026-08-10] the two cross-module READS this trailer recorded (tenant subdomain + timezone through django_apps.get_model) are CLOSED — the writer now lives in the module that owns those rows, and this file imports it; the S61 column spec, period rule and job body stay here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
