# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 task `P3.1`
#          (*"Runs endpoint — a paged read over `jobs` filtered to report
#          kinds, report name joined in. No new table"*). Drawing: p13–p14
#          (the task table) and p39 (screen `5·1`), read as images per B14
#          rule 42. Screens: `5·1` History · `5·2` Run opened.
# Rules:   BR-REP-018 (IS-11 + generated files retained 3 days) · NFR-3
#          (universal server pagination) · NFR-5 (no hard caps) · CLAUDE.md
#          rule 1 (tenant scoping) · B14 rule 31 (no database id on screen)
# Tests:   06-backend/tests/test_cr142_p3_run_history.py
# Impacts: apps/reports/api.py (the two routes) · apps/tenancy/selectors.py
#          (`report_runs` / `report_run`, which own the `jobs` read) ·
#          apps/reports/report_seams.py (how this module reaches them)
# ───────────────────────────────────────────────────────
"""Screen `5·1`'s rows — the run history, over the `jobs` table that exists.

════════════════════════════════════════════════════════════════════════════
WHY THERE IS NO `report_runs` TABLE, AND WHY THAT IS THE DESIGN
════════════════════════════════════════════════════════════════════════════
`apps/reports/exports.py` has carried this sentence since 2026-08-16:

    **A stored run row.** `report_runs` has no B2 anchoring (pack report R-1,
    DDL 🔒), so S45's history is not built. The job record IS the run record
    today — `GET /jobs/{id}` carries who asked, what for and the artifact —
    and the 3-day retention IS the kernel's `ARTIFACT_RETENTION_DAYS`.

The brief agrees with it in the imperative: *"No new table — the job record is
the run record, and the module already says so"*. A second table would be a
second answer to *what has this utility run*, kept in step with the first by
somebody remembering — the shape `bell_events` failed in (DEF-3422).

════════════════════════════════════════════════════════════════════════════
EXPIRY: A ROW OUTLIVING ITS FILE IS THE DESIGNED STATE, NOT AN EDGE CASE
════════════════════════════════════════════════════════════════════════════
BR-REP-018 keeps a generated file for three days; nothing deletes the `jobs`
row. So a run from last month is a real, true, complete record of something
that happened, whose FILE is gone — and the only wrong thing to draw over it is
a download control. That is the same defect as the toast this phase exists to
fix: a live control pointing at nothing (hard-won law 2's mirror).

**Two independent reasons to answer `expired`, and BOTH are asked:**

  · the run's timestamp is older than `ARTIFACT_RETENTION_DAYS` — the RULING's
    own test (*"retention is evaluated against the run's timestamp"*), and the
    one that is true whether or not a sweep has run yet; and
  · the run's export file is not `stored` — its `job_artifacts` row (PO
    2026-10-02, exports in S3) is missing, still `pending`, or stamped
    `deleted` by the daily sweep. The row is the truth about the file; the
    bucket is never asked (a HEAD per row would be fifty calls a page).

⚠ **ASKING ONLY THE FIRST IS A CHECK THAT CANNOT FAIL IN THE SUITE** (law 7):
a run seeded one minute ago would report `ready` with no file behind it and
the assertion would pass over exactly the defect it was written for. Asking
only the SECOND would let a file the sweep has not reached yet outlive the
utility's own setting.

⚠ **AND `expired` IS A DISPLAY STATUS, NEVER A STORED ONE.** Nothing writes it
to `jobs.status`; `core.jobs.STATUSES` is four values and this module invents
none of them. It is derived on read, every read, which is why a row cannot get
stuck saying `ready` because the sweep that would have corrected it never ran.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.reports import exports as report_exports, report_seams

#: The display status a run carries on `5·1`. Four of the five ARE
#: `core.jobs.STATUSES`; `expired` is this module's, derived on read.
RUN_EXPIRED = "expired"

#: The *Any status* select's options, in the order a run passes through them.
#: `core.jobs.STATUSES` is a SET of four and a select needs an order, so the
#: order is declared here — and `expired` is appended because it is the fifth
#: thing a row can say on `5·1` even though nothing ever writes it to a column.
RUN_STATUSES: tuple[str, ...] = ("queued", "running", "ready", "failed", RUN_EXPIRED)

#: The job KINDS a report run may be. One today — the platform's single list
#: export — and a tuple rather than a bare string so a second export kind is a
#: one-line change here instead of a search through this module.
RUN_KINDS: tuple[str, ...] = ("list_export",)


def report_resources() -> tuple[str, ...]:
    """The `payload.resource` values THIS module owns, from the one registry.

    ⚠ **READ FROM `exports.RESOURCES`, NEVER TYPED OUT.** `fire` is what a hand
    -typed second copy of a list costs (CLAUDE.md, B14 rule 2's worked case):
    the row exists, the API serves it, every test passes, and the screen simply
    never shows it. A fifth report registered in `apps/reports/exports.py`
    appears on `5·1` because of this line and for no other reason.
    """
    return tuple(resource.name for resource in report_exports.RESOURCES)


def _retention_days() -> int:
    """How long THIS utility keeps a generated file.

    ⚠ **IT IS A FUNCTION CALL NOW, NOT A CONSTANT READ** (`CR-142-BRC07`
    `P4.6`, 2026-09-27). `BR-REP-018` has said *"3 days by default,
    **tenant-configurable**"* since 2026-08-08 and the configurable half landed
    with the Reports settings section; `apps.tenancy.exports.artifact_retention
    _days()` is the one place that answers it, for the export kernel and for
    this screen alike. Two places computing *how long is a file kept* is two
    places free to disagree, and they would disagree on the day a tenant
    changed it.

    The constant is still the fallback and is read through the same seam, for a
    deployment where the function is not published — `resolve` answers None
    rather than raising, which is `BR-REP-024`'s rule and the reason this file
    may read a neighbour at all.
    """
    settable = report_seams.resolve("tenancy", "artifact_retention_days", kind="exports")
    if settable is not None:
        try:
            days = int(settable())
        except Exception:  # noqa: BLE001 — a screen never falls over a number
            days = 0
        if days >= 1:
            return days
    kernel = report_seams.resolve_constant("tenancy", "ARTIFACT_RETENTION_DAYS", kind="exports")
    return int(kernel) if isinstance(kernel, int) else 3


def _has_stored_file(row: dict[str, Any]) -> bool:
    """Is this run's export file kept? Read off its `job_artifacts` row's state,
    which `tenancy.selectors` stamps on the page in one query."""
    return row.get("artifact_status") == "stored"


def actor_names(rows: list[dict[str, Any]]) -> dict[str, str]:
    """The DISTINCT people who started this page's runs, resolved in one pass.

    ⚠ **`report_seams.resolve` TAKES A `kind` AND TENANCY'S DOES NOT — THAT IS
    WHY THE LOOKUP LIVES HERE.** `apps/tenancy/seams.py`'s resolver imports
    `apps.<module>.services` and nothing else; `user_in_tenant` is one of
    identity's SELECTORS, so resolving it from tenancy answers `None` for every
    row, silently, and the screen says *Schedule* for every run a person
    started. That draft existed and was caught by running the endpoint — the
    story is in `_report_run_row`'s docstring in `apps/tenancy/selectors.py`.

    ⚠ **ONE LOOKUP PER PERSON, NOT ONE PER ROW.** A page is fifty runs and a
    utility has ten to twenty staff, so the distinct set is small and the naive
    shape is fifty queries where two will do.
    """
    found = report_seams.resolve("identity", "user_in_tenant", kind="selectors")
    if found is None:  # pragma: no cover — identity is always published
        return {}
    names: dict[str, str] = {}
    for actor_id in {row.get("started_by_id") for row in rows} - {None}:
        user = found(_tenant_id(), actor_id)
        name = (getattr(user, "full_name", "") or "").strip() if user is not None else ""
        if name:
            names[str(actor_id)] = name
    return names


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def summary(row: dict[str, Any], cache: dict[str, Any] | None = None) -> list | None:
    """The run's parameters IN WORDS, where its report describes them.

    ⚠ **B14 RULE 31.** A report with declared inputs stores ids in its
    filters — Rate Impact's `rows` is a JSON list of schedule and version ids
    and size codes — and History printed them verbatim (walk of 2026-10-12).
    The report that declared them is the one that can name them, so it is
    asked (`MODULE_RUN_SUMMARIES`); every other report answers `None` and the
    screen keeps its one-line reading of plain filters.
    """
    from apps.reports import rate_impact

    describe = rate_impact.MODULE_RUN_SUMMARIES.get(row.get("resource") or "")
    if describe is None:
        return None
    return describe(dict(row.get("filters") or {}), cache)


def present(
    row: dict[str, Any],
    *,
    now: Any = None,
    names: dict[str, str] | None = None,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One selector row as `5·1` draws it — status resolved, file decided.

    ⚠ **`file` IS THE ADDRESS OR `None`, AND THE SCREEN DRAWS A CONTROL ONLY
    WHERE THERE IS ONE.** The two rulings this phase carries are both in this
    one decision: never draw a download over a file that is not there, and let
    a row outlive its file without pretending otherwise.
    """
    moment = now or timezone.now()
    status = row.get("status")
    ran_at = row.get("ran_at")
    display = status
    if status == "succeeded":
        stale = _older_than_retention(ran_at, moment)
        display = RUN_EXPIRED if (stale or not _has_stored_file(row)) else "ready"
    return {
        # ⚠ **THE ID IS IN THE PAYLOAD AND NEVER ON THE SCREEN** (B14 rule 31).
        # It is the address of `5·2` and the address of the file; the row a
        # clerk reads says the report's name and the time it ran.
        "id": row.get("id"),
        "report": row.get("resource"),
        "ran_at": ran_at,
        # ⚠ **A NAME OR `None`, NEVER AN ID** (B14 rule 31). `None` is what the
        # SCREEN renders as *Schedule* — the drawing's own word for a run
        # nobody started by hand — in eleven languages, from the catalogue.
        # ⚠ An id we CANNOT resolve resolves to `None` too, deliberately: a
        # name we cannot produce is not a name, and inventing *Unknown* would
        # be a sixth status nothing ruled.
        "started_by": (names or {}).get(row.get("started_by_id") or ""),
        "filters": row.get("filters") or {},
        "summary": summary(row, cache),
        "status": display,
        "progress": row.get("progress") or {},
        "rows": (row.get("progress") or {}).get("done"),
        "error": row.get("error"),
        "expires_at": _expires_at(ran_at),
        "file": f"/api/exports/{row.get('id')}/file" if display == "ready" else None,
    }


def _older_than_retention(ran_at: Any, now: Any) -> bool:
    moment = _parse(ran_at)
    return False if moment is None else (now - moment) > timedelta(days=_retention_days())


def _expires_at(ran_at: Any) -> str | None:
    """When this run's file goes, as a DATE the screen can render.

    ⚠ **IT IS ARITHMETIC ON THE RUN'S OWN TIMESTAMP, WHICH IS THE RULING.** It
    is served for every run, finished or not, because `5·2` draws an *Expires*
    field and a field that is blank for half its rows is a field that teaches a
    clerk to distrust it.
    """
    moment = _parse(ran_at)
    return None if moment is None else (moment + timedelta(days=_retention_days())).isoformat()


def _parse(value: Any) -> Any:
    if value in (None, ""):
        return None
    from django.utils.dateparse import parse_datetime

    return parse_datetime(str(value))


def runs(**kwargs: Any) -> dict[str, Any]:
    """The paged page of `5·1`, presented. Tenant scoping is the selector's."""
    found = report_seams.resolve("tenancy", "report_runs")
    if found is None:  # pragma: no cover — tenancy is always published
        return {"rows": [], "total": 0, "page": 1, "per": 50, "pages": 0}
    now = timezone.now()
    # ⚠ READ ONCE PER REQUEST, not once per use. Two calls would be two reads of
    # the same settings row in one response, free to disagree if a sibling
    # session saved between them — the cutoff would then cut a page the
    # sentence underneath it contradicts.
    retention_days = _retention_days()
    page = found(
        resources=report_resources(),
        kinds=RUN_KINDS,
        # ⚠ **THE CUTOFF TRAVELS WITH THE QUERY.** A `ready`/`expired` filter is
        # `succeeded` either side of this instant, and the selector cuts the
        # page on it so the pager counts what the filter shows.
        #
        # ⚠ **THE TWO HALVES OF `expired` ARE NOT THE SAME TEST, AND THE
        # DIFFERENCE IS STATED RATHER THAN HIDDEN.** This cutoff is the
        # TIMESTAMP half — the ruling's own test, and the one SQL can apply.
        # `present()` below also asks the FILE half (is the run's export file
        # `stored`), and that one can only ever move a row from `ready` to
        # `expired`, never back. So a page filtered to `ready` may contain a row
        # whose file never finished uploading and presents as `expired` with no
        # download. That is the SAFE direction: the control is withheld, never
        # drawn over nothing. The unsafe direction cannot occur.
        fresh_since=now - timedelta(days=retention_days),
        **kwargs,
    )
    names = actor_names(page["rows"])
    cache: dict[str, Any] = {}
    return {
        **page,
        # `P5.12` — the number screen `5·1`'s retention line states, so the
        # sentence is THIS utility's fact rather than a constant typed into a
        # catalogue. It was `3` in eleven locale files until 2026-09-27, and a
        # tenant that set seven read a true screen saying three.
        "retention_days": retention_days,
        # One cache per page: a run summary reads its report's choices once
        # per services list, not once per row.
        "rows": [present(row, now=now, names=names, cache=cache) for row in page["rows"]],
    }


def run(job_id: Any) -> dict[str, Any] | None:
    """One run, presented — `5·2`'s record. `None` ⇒ a plain 404."""
    found = report_seams.resolve("tenancy", "report_run")
    if found is None:  # pragma: no cover
        return None
    row = found(job_id, resources=report_resources(), kinds=RUN_KINDS)
    return None if row is None else present(row, names=actor_names([row]))


