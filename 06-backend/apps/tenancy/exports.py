# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-008 (EP-SHL-02 — "CSV export": the generic table-level export
#           the PO directed built, 2026-08-09 decision log) · US-AUD-006
#           (EP-AUD-02 — the S61 export whose IS-9 writer this module now hosts
#           for BOTH callers)   Screens: every list that declares Download
#           (S14 · S15 · S26 · S27 · S49 · S9 plans/charges/taxes/history · S61)
# Rules:    BR-SHL-016 (server-side export streamed under the caller's tenant
#           context; >50,000 rows refused; money-table exports write
#           `audit_log`) · BR-SHL-029 (the 50,000 constant) · BR-SHL-011
#           (the export mirrors the list's OWN q/sort/dir/f.‹name› state) ·
#           BR-REP-018 (IS-11 download contract + 3-day retention) ·
#           BR-REP-001 (every money file LABELS its date basis) ·
#           BR-TEN-003 (tenant from context, never client input)
# Tests:    06-backend/tests/test_be_list_export.py (per-TC where US-SHL-008
#           covers it, else test_be_list_export_*)
# Impacts:  apps/audit/exports.py (the S61 writer now delegates here) ·
#           core.jobs handler registry (`list_export`, registered by
#           TenancyConfig.ready) · apps/{metering,assets,rating}/exports.py
#           (the nine registrations) · POST /exports in apps/tenancy/api.py
# ───────────────────────────────────────────────────────
"""The ONE list-export kernel: the IS-9/IS-11 CSV writer + the resource registry.

Two things live here, and nothing else:

**1 · The writer.** UTF-8, comma, exactly ONE header row, stable snake_case
columns, money plain 2dp with no symbol or separator, ISO dates, timestamps in
the tenant's zone WITH the offset, and NO metadata rows in the data — the
context lives in the filename `{tenant}_{report}_{period}_{basis}_{generated}.csv`.
It was authored for S61 (apps/audit/exports.py, 2026-08-10); the generic
endpoint needed the same bytes, so the writer moved HERE rather than being
copied. apps/audit/exports.py imports it and keeps its own column spec, its own
period rule and its own job body — its behavior and its tests are unchanged.

Why tenancy hosts it: this module already hosts the `jobs` table, the BE-07
store/dispatcher and `GET /jobs/{id}` (models.py records that disposition), and
the writer's two non-CSV facts — the tenant's subdomain (the filename's first
segment) and the tenant's timezone (every timestamp) — are tenancy's OWN rows.
Hosting it here turns the audit exporter's two cross-module reads into local
ones; the alternative (leaving it in a feature module and having the platform
import it) would point the dependency the wrong way.

**2 · The resource registry.** One entry per exportable list, registered by the
module that OWNS that list from its `AppConfig.ready()` — the same posture as
lookup handlers (`register_lookup_handler`) and job bodies (`set_job_handler`).
Core and tenancy therefore import no other module's models: an entry carries
callables the owner supplies. An unregistered resource does not exist on this
deployment and answers 404 — never a guessed queryset.

An entry declares, and must declare, everything the endpoint needs to make the
export match the list a user is looking at:

    name        the resource key the client posts ("premises")
    slug        the {report} filename segment
    sorts/default_sort/default_dir/filters   the SAME BR-SHL-011 vocabulary the
                list endpoint passes to parse_list_params — so a sort or filter
                the list honors is honored here, and one it ignores is ignored
                here too (fall back, never 4xx: BR-SHL-011)
    select      params -> the filtered, ordered selection (the SAME selector
                call the list endpoint makes, minus pagination)
    serialize   the SAME row serializer the list endpoint uses (None when the
                selector already returns the served dicts)
    columns     the screen's capability-row columns, in the matrix's order
    money       BR-SHL-016: True for a money-bearing list, whose export writes
                its own `audit_log` row

⚠ **THIS PARAGRAPH SAID IS-9's SECOND HALF WAS NOT IMPLEMENTED UNTIL
2026-09-24 (`P4.13`), AND IT WAS TRUE FOR SIX WEEKS.** It read: *"**Not
implemented, stated rather than papered over:** IS-9's 'current filters AND
VISIBLE COLUMNS'. The ratified body (11b §2.11) carries `resource, filters,
sort, dir, q` and no column state … Every export therefore carries the
capability row's DEFAULT column set, in the matrix's order."*

**RULED, PO 2026-09-24, verbatim: *"all selected columns will go in downloaded
file"*.** The body now carries `columns`, `columns_for()` resolves it, and the
file holds exactly the ticked columns **in the order they were ticked** — the
Export view's ▦ panel is drawn open with an ↑↓ pair per column, so a file that
re-sorted them back would make that panel a lie about its own output.

**BR-SHL-013 is unchanged and is not contradicted by this.** Column visibility
is still a CLIENT preference and the server still stores none; what changed is
that the client now SENDS the preference with the request instead of the server
guessing at it. Omit `columns` and every byte is what it was.
"""

import csv
import logging
import tempfile
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import QuerySet
from django.utils import timezone

from apps.tenancy import models
from core import jobs as core_jobs
from core.pagination import ListParams

logger = logging.getLogger("smartbillhub.exports")

# ⛔ **`EXPORT_ROW_CAP` WAS HERE AND IS DELETED — `P2.4` (`CR-142-BRC07`,
# 2026-09-26). `NFR-5` FORBIDS A HARD CAP ANYWHERE, AND NOTHING MAY PUT ONE
# BACK — NOT HERE, NOT IN A SETTING, NOT ON A SCREEN.**
#
# It read 50,000 from `BR-SHL-016`, then 100,000 from `DEF-MET-5756` on
# 2026-09-18 because a tenant could IMPORT 100,000 premises and then be refused
# the CSV of them. Raising it was the right fix for that day and the wrong
# shape: the number was still short of this product's own customers. **Killeen
# at 57,066 accounts x 14 cycles is ~685,000 bill rows a year**, so a clerk
# asking for their own year was told to narrow their filters.
#
# **DELETING IT COST NOTHING THE WRITER WAS NOT ALREADY DOING.** `write_csv`
# pulls from `row_stream`, which pulls from `selection_iter`, which is
# `.iterator(chunk_size=CHUNK)`: a QuerySet-backed export has always been
# written row by row and never materialised. The cap guarded a danger the
# streaming writer had already removed.
#
# ⚠ **WHAT IS STILL TRUE AND IS NOT THIS COMMIT'S TO FIX.** The derived-filter
# lists (units, assets, routes, cycles and the four rating lists) hand
# `selection_iter` an ALREADY-MATERIALISED list, so those still hold every row
# in memory — with or without a cap, which is why the cap never protected them
# either. That is `NFR-3`'s remaining work on those eight selectors and it is
# recorded here rather than left for the next lane to rediscover.
#
# ⚠ **`apps/audit/services.py` STILL READS `EXPORT_ROW_CAP = 50_000`** under
# `BR-AUD-014`. It is another module's rule and another module's to move; the
# divergence is stated out loud because a divergence nobody wrote down is how
# two rules stopped meaning one value.
LIST_EXPORT_JOB = "list_export"

#: `BR-REP-018` / IS-11: the PLATFORM default a tenant that has never opened
#: Settings gets. ⚠ **IT IS NO LONGER THE WHOLE RULE** (`CR-142-BRC07` `P4.6`,
#: 2026-09-27). The rule has said *"3 days by default, **tenant-configurable**"*
#: since it was signed on 2026-08-08, and the configurable half is now built:
#: `artifact_retention_days()` below is what callers ask, and this is what it
#: answers when the tenant has set nothing. The comment that used to sit here —
#: *"(tenant-config half unbuilt)"* — was true for fifty days and is withdrawn.
ARTIFACT_RETENTION_DAYS = 3
PROGRESS_EVERY = 500  # NFR-4: progress every N rows, not per row
CHUNK = 500
TWO_DP = Decimal("0.01")
MULTI_VALUE_SEPARATOR = "|"  # a list cell inside ONE comma-separated field

# ── IS-9 column kinds ───────────────────────────────────────────────────────
# The kind decides FORMATTING only — never whether a column appears.
TEXT = "text"
MONEY = "money"  # plain 2dp, no symbol, no separators
NUMBER = "number"  # written as served (a count, a multiplier) — see QUANTITY
# ── DEF-1123 · TWO KINDS THAT NEVER EXISTED, AND ONE DELIBERATELY WITHHELD ──
#
# ⚠ **A CSV IS A READING SURFACE IN THIS PRODUCT, RULED BY THE PO ON 2026-08-27
# (OQ-620(b)), AND THAT RULING OVERRULED THE RECOMMENDATION.** Verbatim: *"Is a
# downloaded CSV read by a person or calculated by a spreadsheet? (a) Two
# decimals, like the screen - this is okay"*. What was shown to them was the
# argument AGAINST: that the reads export writes `1008.000000` today and a
# tenant's downstream spreadsheet may depend on it. They chose the screen
# anyway, with that stated.
#
# Until this commit IS-9 had no QUANTITY kind at all, so every quantity fell
# through to NUMBER — the comment above used to read *"a count, a multiplier, a
# percent"* — and the reads export wrote `prior_value`, `current_value` and
# `consumption` at BR-MET-019's storage precision. There was no PERCENT kind
# either, so a percentage exported at its stored six places against hard rule
# 2's display two.
#
# Worked, from the ruling: `1008.000000` -> `1008`; `26.243700` -> `26.24`; a
# money column `64.5700` -> `64.57`.
QUANTITY = "quantity"  # BR-MET-144: at most 2dp, half-up, trailing zeros TRIMMED
#
# ⚠ **THERE IS NO `PERCENT` KIND, AND THIS PARAGRAPH IS WHY — I ADDED ONE AND
# TOOK IT BACK OUT (OQ-621).** DEF-1123 reported that IS-9 had no PERCENT kind
# and that percentages therefore exported at six places against hard rule 2.
# The kind was written, and then the only exported percent column in the
# product turned out to hold a **FRACTION** — `charges.percent` stores
# `0.015000` for one and a half percent — so quantizing it to two places would
# have written `0.02` and destroyed the value. `test_be_list_export.py` had the
# reason in its own assertion and caught it on the first run.
#
# That leaves the kind with **no call site at all**, which is hard-won law 2
# (built is not wired) and would be dead code carrying a trap: the next lane to
# meet a percent column would find a ready-made kind and no way to tell that it
# is only safe on POINTS. So it is gone, and the real question — the file
# writes `0.015000` where the SCREEN renders `1.50%`, a difference of UNIT and
# not of precision — is **OQ-621**, because OQ-620(b) ruled on precision and
# rescaling a column by 100 is not a precision decision.
#
# ⚠ **THERE IS NO `RATE` KIND HERE YET AND ITS ABSENCE IS A DECISION, NOT AN
# OMISSION — DO NOT ADD ONE BY GUESSING.** OQ-620(a) ruled that a tariff RATE
# displays FOUR decimals with its zeros KEPT (`$0.1420`), so the screen now
# shows THREE precisions and *"two decimals, like the screen"* no longer names
# a single number. The coherent reading is that each kind follows its own
# screen rule in the file too, so a rate would export `0.1420` and not `0.14`
# — and that reading is RECORDED AND PUT BACK TO THE PO for one line of
# confirmation rather than taken here, because the alternative (every column at
# exactly two places) exports a rate that cannot reproduce its own line, which
# is the precise hazard OQ-620(a) exists to prevent. Until that line comes
# back, a rate column declares MONEY or NUMBER and says which in its own
# comment; the moment it is confirmed, `wording.rate_text` is the one composer
# to delegate to (BR-SHL-250 §4).
DATE = "date"  # ISO date, as the serializer already emits it
TIMESTAMP = "timestamp"  # tenant TZ, ISO 8601, WITH the offset
BOOLEAN = "boolean"  # true / false — machine-parseable, never Yes/No copy
LIST = "list"  # multi-value cell, joined with MULTI_VALUE_SEPARATOR


# ── IS-9 value formatting ───────────────────────────────────────────────────
def format_money(value: Any) -> str:
    """IS-9 money: plain 2dp, no symbol, no separators.

    DISPLAY rounding only — B4's half-up-at-finalization law belongs to the
    invoice line, not to this writer; a value that reaches here is already
    whatever its owner made it (CLAUDE.md rule 2: round at finalization or
    display). Anything that is not a number is written through UNCHANGED,
    because an export must never quietly turn a value into something else.
    """
    if value is None:
        return ""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return str(amount.quantize(TWO_DP, rounding=ROUND_HALF_UP))


def format_quantity(value: Any) -> str:
    """IS-9 quantity: BR-MET-144, at most 2dp, half-up, trailing zeros TRIMMED.

    `1008.000000` -> `1008` · `26.243700` -> `26.24`. **Not padded** — that is
    where a quantity differs from money in this same file, and reaching for
    `format_money` instead writes `1008.00`, which is a well-formed string and
    the wrong rule.

    ⚠ **DELEGATED, NOT RE-DERIVED (BR-SHL-250 §4).** `apps.metering
    .quantity_display.quantity_text` is the composer the SCREEN uses, so the
    file and the screen cannot drift — which is the entire content of the PO's
    ruling. Anything unparseable is written through unchanged, exactly as
    `format_money` does and for the same reason.
    """
    if value is None:
        return ""
    from apps.metering import quantity_display

    text = quantity_display.quantity_text(value)
    return "" if text is None else text


def format_when(moment: Any, tz: ZoneInfo) -> str:
    """IS-9 timestamps: the tenant's timezone, ISO 8601, WITH the offset.

    Accepts a datetime or the ISO string a serializer already produced (every
    list selector here serves `.isoformat()` strings). A value that cannot be
    parsed is written through unchanged — see format_money's reasoning.
    """
    if moment is None:
        return ""
    if isinstance(moment, str):
        try:
            moment = datetime.fromisoformat(moment)
        except ValueError:
            return moment
    if not isinstance(moment, datetime):
        return str(moment)
    if timezone.is_naive(moment):
        moment = moment.replace(tzinfo=datetime_timezone.utc)  # storage is UTC (B2)
    return moment.astimezone(tz).isoformat()


def format_date(value: Any) -> str:
    """IS-9 dates: ISO. The serializers already emit ISO strings; a real date
    object is rendered the same way rather than through str()."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def format_list(value: Any) -> str:
    """A multi-value cell inside ONE comma-separated field. Joined with `|`
    (not a comma) so the cell can never be misread as extra columns."""
    if value is None:
        return ""
    if isinstance(value, (str, bytes)):
        return str(value)
    if isinstance(value, Iterable):
        return MULTI_VALUE_SEPARATOR.join("" if item is None else str(item) for item in value)
    return str(value)


def format_boolean(value: Any) -> str:
    """`true` / `false`. Not "Yes"/"No": that is COPY, and copy is the UI's
    (IS-8 renders it in the tenant's language; a CSV must stay parseable)."""
    if value is None:
        return ""
    return "true" if bool(value) else "false"


def format_value(value: Any, kind: str, tz: ZoneInfo) -> str:
    if kind == MONEY:
        return format_money(value)
    if kind == QUANTITY:
        return format_quantity(value)
    if kind == TIMESTAMP:
        return format_when(value, tz)
    if kind == DATE:
        return format_date(value)
    if kind == LIST:
        return format_list(value)
    if kind == BOOLEAN:
        return format_boolean(value)
    return "" if value is None else str(value)


# ── the tenant facts the filename and the timestamps need (LOCAL rows) ──────
def tenant_timezone(tenant_id: Any) -> ZoneInfo:
    """The tenant's IANA zone (Settings → Regional), UTC when unset/unknown.

    UTC is the honest fallback: storage is UTC (B2), so an unset tenant zone
    exports the stored instant rather than a guessed local one.
    """
    name = (
        models.TenantSettings.objects.filter(tenant_id=tenant_id)
        .values_list("timezone", flat=True)
        .first()
    )
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("tenant %s has an unusable timezone %r — exporting in UTC", tenant_id, name)
        return ZoneInfo("UTC")


def tenant_slug(tenant_id: Any) -> str:
    """The {tenant} filename segment: the subdomain."""
    subdomain = (
        models.Tenant.objects.filter(id=tenant_id).values_list("subdomain", flat=True).first()
    )
    return subdomain or "tenant"


def period_segment(filters: Mapping[str, Any], *, default: str) -> str:
    """The {period} filename segment, derived from the caller's OWN range.

    An explicit range inside one month reads as that month (`2026-08`); any
    other explicit range names both ends; with no range the file covers the
    whole list the filters selected and says so with the resource's default
    segment. Same rule the S61 export applies to its own window.
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
        return (start or end)[:7]
    return default


def artifact_filename(
    tenant_id: Any,
    *,
    report: str,
    period: str,
    basis: str,
    now: datetime,
    tz: ZoneInfo,
) -> str:
    """IS-11: `{tenant}_{report}_{period}_{basis}_{generated}.csv`."""
    generated = now.astimezone(tz).strftime("%Y%m%dT%H%M")
    return "_".join((tenant_slug(tenant_id), report, period, basis, generated)) + ".csv"


# ── where a finished export IS vs where it is SERVED (S3, PO 2026-10-02) ─────
# ⚠ **THERE IS NO ARTIFACTS DIRECTORY ANY MORE — `DEF-MET-4954`.** Until
# 2026-10-02 this section was `artifacts_dir()` (`settings.JOB_ARTIFACTS_DIR`),
# and the job record carried `payload["artifact_path"]`: an absolute path on
# the disk of whichever container ran the job. With `JOBS_EAGER=false` that is
# a WORKER, and the web process serving the download looked in its own empty
# folder of the same name and answered 404 — every export, every time — until a
# shared Docker volume papered over it. PO, 2026-10-02 (decision log, *"EXPORT
# FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*): *"Removed
# -> Yes we will just be using S3"*.
#
# Now a job body writes its file into a SCRATCH folder of its own
# (`scratch_dir()`), hands it to `finish_artifact`, and the folder is deleted
# when the `with` closes — on success and on failure. `finish_artifact` stores
# the file at `t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>` through
# `apps/tenancy/export_store.py` and records it in a `job_artifacts` row;
# everything that serves, lists or sweeps the file reads THAT row.
#
#   `result_link`  the HTTP route a browser can follow — GET /api/exports/{id}/file.
#                  Unchanged: the frontend's anchor needs nothing new.
#   job_artifacts  the row: which utility, the exact key, the file name, size,
#                  hash and status. Never served to a client.
# PLATFORM path — no tenant segment (PO ruling 2026-08-10, path tenancy):
# the download is scoped by the session the caller presents, not by the URL.
DOWNLOAD_PATH_TEMPLATE = "/api/exports/{job_id}/file"
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"  # IS-9 writes UTF-8, always
ZIP_CONTENT_TYPE = "application/zip"


def scratch_dir() -> tempfile.TemporaryDirectory:
    """A private folder for ONE job body to build its file in.

    Used as `with scratch_dir() as folder:` — the folder and everything in it
    are removed when the block closes, whether the job succeeded or raised, so
    no export is ever left on a container's disk (`DEF-BIL-9148` was the print
    set's ZIP being built in the SHARED folder instead).
    """
    return tempfile.TemporaryDirectory(prefix="export-")


def download_path(job_id: Any) -> str:
    """The IS-11 download route for one finished export job."""
    return DOWNLOAD_PATH_TEMPLATE.format(job_id=job_id)


# Which job kinds may be downloaded through that route. `list_export` is this
# module's own; every other owner registers its kind from AppConfig.ready() —
# the same posture as the resource registry above, so the platform never
# hardcodes another module's job vocabulary.
_download_kinds: set[str] = {LIST_EXPORT_JOB}


def register_export_kind(kind: str) -> None:
    """Declare `kind` downloadable at GET /api/exports/{job_id}/file."""
    _download_kinds.add(str(kind))


def downloadable_kinds() -> tuple[str, ...]:
    """Every downloadable job kind on THIS deployment, sorted (tests + support)."""
    return tuple(sorted(_download_kinds))


def finish_artifact(
    job_id: Any, path: Path, *, tenant_id: Any, content_type: str = CSV_CONTENT_TYPE
) -> str:
    """Store the finished file, record it, return WHERE IT IS SERVED.

    One place, because every export job body owes both facts. `path.name` IS
    the IS-11 filename the writer composed, and it becomes the row's
    `display_name` — what the browser saves the file as.
    """
    from apps.tenancy import export_store

    export_store.publish(
        job_id=job_id,
        tenant_id=tenant_id,
        path=Path(path),
        display_name=Path(path).name,
        content_type=content_type,
    )
    return download_path(job_id)


def resolve_artifact(job: Mapping[str, Any] | None) -> Any:
    """The `job_artifacts` row GET /api/exports/{job_id}/file may hand over, or None.

    Five independent reasons to answer None, and every caller renders every one
    of them as the SAME plain 404 (HR-1 / 11b G4 — existence must not leak, and
    a 403 or a distinguishable message would confirm it):

      · the id is absent under the caller's tenant scope (job is None)
      · the job is not an export kind
      · it has not SUCCEEDED — an unfinished file must never be served
      · it has no stored file (written before 2026-10-02, or never uploaded)
      · the file is past the utility's `file_retention_days`, read NOW
        (BR-TEN-043) — whether or not the daily sweep has removed it yet
    """
    from apps.tenancy import export_store

    if job is None:
        return None
    if job.get("kind") not in _download_kinds:
        return None
    if job.get("status") != core_jobs.SUCCEEDED:
        return None
    row = export_store.for_job(job.get("id"))
    return row if export_store.available(row) else None



def log_missing_artifact(job: Mapping[str, Any] | None) -> None:
    """Say, at ERROR, why a SUCCEEDED export has nothing to hand over (DEF-TEN-9190).

    Called only on the refusal path of the download. An unknown, foreign,
    unfinished or expired job logs nothing — those are ordinary. A job whose
    record says `succeeded` and which has no `stored` row is not ordinary: the
    worker that ran it either never published to S3 (a build before 2.455.0
    writes to its own disk) or its file was swept. The caller still answers the
    one plain 404 (HR-1); only the log is different.
    """
    from apps.tenancy import export_store

    if job is None or job.get("kind") not in _download_kinds:
        return
    if job.get("status") != core_jobs.SUCCEEDED:
        return
    row = export_store.for_job(job.get("id"))
    if row is None:
        logger.error(
            "export %s: the job SUCCEEDED but no file was ever recorded for it. The worker "
            "that ran it did not publish to S3 - the usual cause is a celery image older "
            "than 2.455.0 (which writes exports to its own disk). Rebuild and restart every "
            "celery service on the same build as web.",
            job.get("id"),
        )
    elif row.status != export_store.STATUS_STORED:
        logger.error(
            "export %s: the job SUCCEEDED but its file is %r at %s, not stored",
            job.get("id"), row.status, row.storage_key,
        )


def artifact_retention_days(
    tenant_id: Any = None, *, default: int = ARTIFACT_RETENTION_DAYS
) -> int:
    """How long THIS tenant keeps a generated file (`BR-REP-018`, `P4.6`).

    The tenant's own `file_retention_days` from the `reports` settings family,
    or the platform default when nothing is set, when no settings row exists
    yet, or when this is called outside a tenant context (a management command,
    a migration, the sweep that runs before a job resolves its tenant).

    ⚠ **A CALLER THAT ALREADY HOLDS THE TENANT PASSES IT**, which is
    `BR-TEN-043`'s shape one noun over: a function that re-derives a fact its
    caller was handed is a second answer free to disagree with the first.
    `run_list_export_job` has `record["tenant_id"]` in its hand; the request
    path does not, and reads the context instead.

    ⚠ **IT NEVER RAISES AND IT NEVER RETURNS ZERO OR LESS.** This function is
    called on the read path of every run row on screen `5·1` and on the way
    into every export. A settings read that throws would take a whole screen
    down over a number whose safe answer is already known, and a retention of
    zero is not a shorter window — it is *every download link in the product is
    broken*. `settings_families` refuses anything under 1 on the way in; this
    is the second belt, for a row written before that minimum existed.

    ⚠ **AND IT IS READ AT EVENT TIME, NEVER CACHED** — `BR-TEN-043`. Retention
    is evaluated against a run's timestamp and is not stored on it, so lowering
    the setting makes yesterday's file unavailable the moment the row is saved.
    Nothing is deleted by that save and no job re-runs.
    """
    try:
        from apps.tenancy import models as tenancy_models

        whose = tenant_id if tenant_id is not None else _current_tenant_id()
        if whose is None:
            return default
        stored = (
            tenancy_models.TenantSettings.objects.filter(tenant_id=whose)
            .values_list("reports", flat=True)
            .first()
        )
    except Exception:  # noqa: BLE001 — see the docstring: never take a screen down
        return default
    value = (stored or {}).get("file_retention_days")
    try:
        days = int(value)
    except (TypeError, ValueError):
        return default
    return days if days >= 1 else default


def default_download_format(tenant_id: Any = None, *, default: str = "csv") -> str:
    """What a download IS unless the clerk asks otherwise (`BR-REP-018`, `P4.6`).

    The tenant's own `default_download_format`, or the platform default when
    nothing is stored. Same posture as `artifact_retention_days` above: it never
    raises, and it never answers a value the product cannot produce — an
    unrecognised string falls back rather than reaching a writer that has no
    branch for it.

    ⚠ **THERE IS EXACTLY ONE FORMAT TODAY AND THAT IS NOT AN ACCIDENT.**
    `apps.reports.models.FORMATS` is `("csv",)` because no PDF renderer is
    declared anywhere in this product. This function exists so that the day one
    is, the tenant's choice already has a reader — not so that a second value
    can be smuggled in without one.
    """
    try:
        from apps.tenancy import models as tenancy_models

        whose = tenant_id if tenant_id is not None else _current_tenant_id()
        if whose is None:
            return default
        stored = (
            tenancy_models.TenantSettings.objects.filter(tenant_id=whose)
            .values_list("reports", flat=True)
            .first()
        )
    except Exception:  # noqa: BLE001 — never take a screen down over a label
        return default
    value = (stored or {}).get("default_download_format")
    return str(value) if isinstance(value, str) and value else default


def _current_tenant_id() -> Any:
    """This request's tenant, or None outside one. Never guesses."""
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


# ⚠ **`purge_expired` IS GONE, AND SO IS "DELETE ON THE NEXT EXPORT"** (PO
# 2026-10-02: *"Once a day, for each utility, the system deletes exports older
# than that utility's own setting"*). Old files are removed by
# `apps/tenancy/export_store.sweep_tenant`, run daily per utility by
# celery-beat (`apps/tenancy/export_sweep.py`). It keeps `DEF-TEN-9146`'s rule
# — a utility is required and there is no all-utilities form — and it can
# delete nothing but that utility's own `export/` files.


# ── the streamed writer both callers share ──────────────────────────────────
def write_csv(
    path: Path,
    header: Iterable[str],
    rows: Iterator[tuple[list[str], Any]],
    *,
    job_id: Any = None,
    total: int | None = None,
    checkpoint_of: Callable[[Any], Any] | None = None,
    footer: Sequence[str] | None = None,
) -> int:
    """Stream `rows` into `path` under the IS-9 contract. Returns rows written.

    One header row, then the data. Rows arrive from a generator so a
    50,000-row export never materializes a 50,000-row list. Progress is
    recorded every PROGRESS_EVERY rows (NFR-4) when a job id is supplied;
    `checkpoint_of` turns the last written row into the resume marker TD-17
    asks every job body to keep.

    ⚠ **`footer` IS `P2.22`, AND IT IS A KNOWN TENSION WITH `IS-11` THAT IS
    REPORTED RATHER THAN RESOLVED HERE.** This docstring read *"nothing else
    ever goes in the file"* and `BR-REP-018` says *"no metadata rows"*. `P2.22`
    says a total that cannot lawfully be summed shows an em-dash and its reason
    *"on screen **and in the CSV**"*. Both are signed and they disagree, so per
    hard-won law 13 the supersession is PUT TO THE PO and never assumed —
    `OQ-REP-12740`.

    **What ships meanwhile is the reading that cannot produce a wrong number in
    either direction:** `footer` is passed ONLY when the file would otherwise
    have carried a figure that is not lawful. Every export whose totals are all
    lawful — which is all nine lists and every report as it ships today —
    passes `None` and is byte-identical to the file it wrote yesterday. So
    IS-11 is intact everywhere it is currently true, and the only files that
    gain a row are the ones whose alternative is an auditor reading a number
    that means nothing.

    It is NOT counted in the return value: `written` is a count of DATA rows,
    and a caller comparing it against a row count must not be handed a number
    one larger because a total refused itself.
    """
    written = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(header))  # exactly one header row (IS-9)
        for cells, source in rows:
            writer.writerow(cells)
            written += 1
            if job_id is not None and written % PROGRESS_EVERY == 0:
                core_jobs.record_progress(
                    job_id,
                    done=written,
                    total=total,
                    checkpoint=(None if checkpoint_of is None else checkpoint_of(source)),
                )
        # ⚠ INSIDE the `with`, after the last data row. See the docstring.
        if footer:
            writer.writerow(list(footer))
    if job_id is not None:
        core_jobs.record_progress(job_id, done=written, total=total)
    return written


# ── the resource registry ───────────────────────────────────────────────────
@dataclass(frozen=True)
class ExportColumn:
    """One CSV column: its stable snake_case header, where the value comes
    from, and how IS-9 formats it.

    `source` is a key of the served row dict, or a callable over it for a value
    the screen composes from more than one field. A column whose ratified name
    has no API field behind it uses the API field name — recorded per resource.
    """

    name: str
    source: str | Callable[[Mapping[str, Any]], Any]
    kind: str = TEXT

    def value(self, row: Mapping[str, Any]) -> Any:
        if callable(self.source):
            return self.source(row)
        return row.get(self.source)


@dataclass(frozen=True)
class ExportResource:
    """One exportable list. Registered by the module that owns the list."""

    name: str
    slug: str
    module: str
    select: Callable[[ListParams], Any]
    columns: tuple[ExportColumn, ...]
    serialize: Callable[[Any], Mapping[str, Any]] | None = None
    sorts: tuple[str, ...] = ()
    default_sort: str | None = None
    default_dir: str = "asc"
    filters: tuple[str, ...] = ()
    money: bool = False
    #: `P2.22` — given this run's params and the chosen columns, the ONE row to
    #: append, or `None`. Returns `None` whenever every total is lawful, which
    #: is what keeps every existing file byte-identical (see `write_csv`).
    footer: Callable[[ListParams, tuple["ExportColumn", ...]], Sequence[str] | None] | None = None
    # BR-REP-001: a money KPI must label its date basis. None of these lists is
    # one, so the segment says WHAT KIND of file this is instead of naming a
    # basis it does not have (`event-time` for an append-only log, the
    # resource's own default otherwise). Flagged to the PO batch as a candidate
    # filename-vocabulary row rather than invented as law.
    basis: str = "current-state"
    period: str = "full-list"
    #: Checks THIS resource's own parameters and raises the caller's
    #: `ValidationError`, without reading a row. Run by `request_list_export`
    #: BEFORE the job exists (DEF-TEN-9160): a malformed date or a missing
    #: subject is refused at the door with its field named, never accepted and
    #: then failed in a worker nobody is watching. `None` = nothing to check.
    validate: Callable[[ListParams], None] | None = None
    #: `CR-192-BRC10` task 13 — columns that exist only because of THIS run's
    #: rows (a utility's own read-format questions), appended after the chosen
    #: set. Given the params and the selection, never a list of rows: it asks
    #: the database which questions the selection carries (NFR-3). `None` =
    #: the file is exactly the chosen columns, as for every other resource.
    extra_columns: (
        Callable[[ListParams, Any], tuple["ExportColumn", ...]] | None
    ) = None

    @property
    def header(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


_resources: dict[str, ExportResource] = {}


def register_export_resource(resource: ExportResource) -> None:
    """Owner modules call this from AppConfig.ready(). Re-registration replaces
    (a reloaded app registry must not raise), and is logged so a silent second
    owner cannot appear without a trace."""
    if resource.name in _resources and _resources[resource.name] is not resource:
        logger.info("export resource %r re-registered by %s", resource.name, resource.module)
    _resources[resource.name] = resource


def export_resource(name: str) -> ExportResource | None:
    """The registered resource, or None — the caller turns None into a 404."""
    return _resources.get(str(name or ""))


def registered_resources() -> tuple[str, ...]:
    """Every exportable list on THIS deployment, sorted. Used by the tests and
    by anyone asking "what can be exported" without reading nine apps."""
    return tuple(sorted(_resources))


def columns_for(resource: ExportResource, chosen: Any = None) -> tuple[ExportColumn, ...]:
    """The columns THIS file carries — the caller's ticked set, or the default.

    ⚠ **THIS IS THE HALF THIS MODULE'S OWN DOCSTRING SAID WAS NOT IMPLEMENTED
    UNTIL 2026-09-24 (`P4.13`).** It read: *"IS-9's 'current filters AND
    VISIBLE COLUMNS' … the ratified body … carries no column state … Every
    export therefore carries the capability row's DEFAULT column set"*. That
    was true and honestly stated for six weeks. **RULED, PO 2026-09-24,
    verbatim: *"all selected columns will go in downloaded file"*** — so the
    body carries `columns` now, and this is where it is honoured.

    **THE ORDER IS THE CALLER'S, not the matrix's** (Finance blueprint p070
    row 5: *"the ticked columns, in their order"*). The ▦ chooser on the
    Export view is drawn OPEN with an ↑↓ pair per column; a file that re-sorted
    them back into the matrix's order would make that panel a lie about its own
    output.

    **BR-SHL-011 governs everything unrecognised, verbatim — *"fall back,
    never 4xx"*.** An unknown name is dropped. A value that is not a list is
    ignored whole. And a request naming ONLY unknown columns gets the DEFAULT
    set rather than an empty one, because a zero-column CSV is a file whose
    every row is blank — a worse answer than ignoring the request.

    Duplicates collapse to the first occurrence: two identically-named headers
    are a file a spreadsheet opens with two columns nobody can tell apart.
    """
    by_name = {column.name: column for column in resource.columns}
    picked: list[ExportColumn] = []
    seen: set[str] = set()
    if isinstance(chosen, (list, tuple)):
        for raw in chosen:
            if not isinstance(raw, str):
                continue
            name = raw.strip()
            if name in by_name and name not in seen:
                seen.add(name)
                picked.append(by_name[name])
    return tuple(picked) if picked else resource.columns


# ── streaming a selection (queryset or list, one code path) ─────────────────
#
# ⛔ **`selection_count(selection)` WAS HERE AND IS DELETED WITH THE CAP
# (`P2.4`).** It existed for two readers: the refusal, which is gone, and the
# job's progress TOTAL, which `record_progress` already accepts as `None`. For
# a QuerySet it was a `COUNT`; for the derived-filter lists it fell through to
# `len()` on an already-materialised list, **so the whole report was built
# once to be counted, thrown away, and built again to be written**. On a
# 40,000-row ageing at T5 that was the entire cost of the export, doubled, for
# a number the clerk does not need before the file exists.
#
# A progress bar without a denominator counts up instead of filling, which is
# what a stream honestly has. Do not reintroduce a count to make it fill.
def selection_iter(selection: Any) -> Iterator[Any]:
    """Stream the selection. A QuerySet is pulled with .iterator() so the file
    is written row by row; an already-materialized list is iterated as is."""
    if isinstance(selection, QuerySet):
        return selection.iterator(chunk_size=CHUNK)
    return iter(selection)


def row_stream(
    resource: ExportResource,
    selection: Any,
    tz: ZoneInfo,
    columns: tuple[ExportColumn, ...] | None = None,
) -> Iterator[tuple[list[str], Any]]:
    """(formatted cells, source row) for every row of the selection.

    `columns` is `columns_for(resource, …)`'s answer — the caller's ticked set
    (`P4.13`). It defaults to the resource's own, so every caller that predates
    the column chooser keeps writing byte-identical files. **The cells are
    built from the SAME tuple the header was built from**, which is what stops
    a reordered header arriving over unreordered cells — a file where every
    column is mislabelled and every value is real.
    """
    chosen = resource.columns if columns is None else columns
    for source in selection_iter(selection):
        served = source if resource.serialize is None else resource.serialize(source)
        yield [format_value(column.value(served), column.kind, tz) for column in chosen], served


def _checkpoint_of(row: Any) -> Any:
    """TD-17 resume marker: the row's id when the served shape has one."""
    if isinstance(row, Mapping):
        return row.get("id")
    return getattr(row, "id", None)


# ── the job body (BE-07 runner contract: record -> result_link) ─────────────
def run_list_export_job(record: dict[str, Any]) -> str:
    """Write ONE list's CSV and return its result link.

    Runs under the record's tenant context (core.jobs.run_job entered it), so
    the query behind the file is the caller's own tenant's — BR-SHL-016 "under
    the caller's tenant context", enforced by RLS on Postgres and by the
    explicit tenant filter every selector applies on every tier.

    **There is no cap to check, at accept time or here — `P2.4` deleted it and
    `NFR-5` forbids putting one back.** The file streams, so its size is
    bounded by the tenant's own data and by nothing else.

    `total=None` is passed to `write_csv` deliberately: nothing has counted the
    selection, because counting it was a second full build of the report. The
    progress record carries `done` and no denominator until the job finishes,
    at which point `written` is the exact figure — measured from what was
    written rather than predicted before the file existed.
    """
    payload = record.get("payload") or {}
    tenant_id = record["tenant_id"]
    resource = export_resource(payload.get("resource"))
    if resource is None:
        # Only reachable if a module were unregistered between accept and run.
        # The record carries the failure; nothing writes a half-named file.
        raise core_jobs.JobsError(f"no export resource registered for {payload.get('resource')!r}")

    params = params_from_payload(resource, payload)
    selection = resource.select(params)

    tz = tenant_timezone(tenant_id)
    # The file is built in a SCRATCH folder of this job's own and stored in S3
    # by `finish_artifact`; the folder is removed when the `with` closes, on
    # success and on failure (PO 2026-10-02 — no export lives on a disk).
    # Old files are no longer swept here: the daily per-utility sweep does it.
    with scratch_dir() as folder:
        path = Path(folder) / artifact_filename(
            tenant_id,
            report=resource.slug,
            period=period_segment(params.filters, default=resource.period),
            basis=resource.basis,
            now=timezone.now(),
            tz=tz,
        )

        # P4.13 — the ticked columns, in their order. ONE resolution, used for
        # the header AND for the cells, so the two cannot disagree.
        chosen = columns_for(resource, payload.get("columns"))
        if resource.extra_columns is not None:
            chosen = chosen + tuple(resource.extra_columns(params, selection))
        written = write_csv(
            path,
            tuple(column.name for column in chosen),
            row_stream(resource, selection, tz, columns=chosen),
            job_id=record["id"],
            # `P2.4` — no pre-count, so no denominator. See the docstring.
            total=None,
            checkpoint_of=_checkpoint_of,
            # `P2.22` — `None` unless a total refused itself. See `write_csv`.
            footer=None if resource.footer is None else resource.footer(params, chosen),
        )
        # DEF-TEN-9190 — the job id is in the line so the build and the upload
        # that follows (`export_store.publish`) read as one story in the log.
        logger.info(
            "export %s: built %s, %s row(s) in %s", record["id"], resource.name, written, path.name
        )
        # IS-11: the link is the DOWNLOAD ROUTE, never a path or a bucket key.
        return finish_artifact(record["id"], path, tenant_id=tenant_id)


def params_from_payload(resource: ExportResource, payload: Mapping[str, Any]) -> ListParams:
    """Rebuild the caller's list state from the job payload.

    Stored as plain strings on the record (a job payload is JSON), rebuilt into
    the SAME ListParams the list endpoint hands its selector — so the job re-runs
    the caller's query, not an approximation of it.
    """
    return ListParams(
        q=str(payload.get("q") or ""),
        sort=payload.get("sort") or resource.default_sort,
        dir=str(payload.get("dir") or resource.default_dir),
        filters={str(k): str(v) for k, v in (payload.get("filters") or {}).items()},
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-008@17df6a0 (EP-SHL-02 §Stories — hash = sha256/7 of the source epic; co-packet US-AUD-006@009e809 for the writer this module now hosts)
# generated: 2026-08-10 by story-coder v1 (list-export lane — the generic POST /exports the PO directed, built on the job runner that landed the same day) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — this module is the kernel; its resource is POST /exports in api.py) E=deferred(no-frontend-half — the nine screens are wired in 07-frontend) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: IS-9's "current filters AND VISIBLE COLUMNS" is HALF implemented — the ratified body (11b §2.11) carries no column state and per-user column visibility is a client preference (BR-SHL-013), so every export carries the capability row's DEFAULT column set — REPORTED, not guessed · the filename follows IS-11's five-segment `{tenant}_{report}_{period}_{basis}_{generated}.csv` (the later PO-confirmed form, and the one the S61 writer already emits) rather than US-SHL-008 §5's older `‹screen›-‹tenant›-‹YYYYMMDD›.csv` — ONE writer cannot honor two filename laws; divergence REPORTED · BR-REP-001's date-basis label has no value for a non-money list, so the {basis} segment states the KIND of file (`current-state` / `event-time`) instead of naming a money basis it does not have — flagged to the PO batch as a candidate vocabulary row · BR-SHL-016 says "synchronous streamed download"; 11b §2.11 (later, ratified) says 202 + job_id, which is what this implements — the divergence is the contract's, recorded not resolved · no DOWNLOAD endpoint exists (IS-11 downloads are the reports W5 story), so result_link is a `file:` artifact reference · retention is a best-effort sweep on each export because celery-beat is TD-17, and BR-REP-018's "tenant-configurable" half has no storage — REPORTED · [path-tenancy lane 2026-08-10] DOWNLOAD_PATH_TEMPLATE is now `/api/exports/{job_id}/file`, a PLATFORM path with no tenant segment — scoped by the caller's session, like the poll beside it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
