# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 tasks `P4.2` (the
#          scheduler), `P4.3` (recipients — internal staff only) and `P4.7`
#          (cadence arithmetic, all four cases). Drawings: p14–p15 (the task
#          table), p34 (screen `2·3`), p40 (screen `4·1`), read as IMAGES per
#          B14 rule 42. Screens: `2·3` · `4·1` · `4·2`.
# Rules:   BR-REP-020 CONFIRMED (*"Scheduled-report recipients: INTERNAL staff
#          only in v1; EXTERNAL recipients arrive at W6 with an explicit
#          confirm step — external send = data leaves the tenant"*) ·
#          BR-REP-018 (IS-11 downloads; generated files retained 3 days) ·
#          BR-TEN-022 (an accounting period is COMPUTED from the tenant's
#          fiscal settings, never stored) · BR-TEN-081 / BR-TEN-043 (the
#          utility's OWN clock decides what day it is) · CLAUDE.md hard rule 1
#          (tenant scoping — and this file runs OUT OF REQUEST, which is where
#          that context is lost) · hard rule 6 (idempotency) · hard rule 7
#          (every money action writes `audit_log`) · hard-won law 2 (built is
#          not wired) · law 7 · law 14
# Tests:   06-backend/tests/test_cr142_p4_schedules.py
#          06-backend/tests/test_cr142_p4_schedules_pg.py  ⚠ the RLS half, and
#          it MUST run on real PostgreSQL — see the header block below.
# Impacts: apps/reports/models.py (`ReportSchedule`) · apps/reports/api.py (the
#          five routes) · apps/reports/apps.py (`ready()` calls `install()`) ·
#          apps/reports/report_seams.py (`live_tenants`, `user_list`,
#          `tenant_timezone` — three reads this module did not have).
#          ⚠ NOT docker-compose.yml: `celery-beat` is ALREADY deployed and
#          three modules already install entries this way — see `install()`.
# ───────────────────────────────────────────────────────
"""The scheduler: a report runs on Monday because somebody said so on Friday.

════════════════════════════════════════════════════════════════════════════
IT ENQUEUES THE JOB THE EXPORT BUTTON ALREADY ENQUEUES — `list_export`
════════════════════════════════════════════════════════════════════════════
A scheduled run is not a second kind of run. `run_history.RUN_KINDS` is
`("list_export",)` and screen `5·1` reads it, so a schedule that invented its
own job kind would produce files **that never appear in the run history** —
live work behind a list that cannot see it, which is hard-won law 2's mirror
wearing a server costume. So this module calls the same accept path a clerk's
Export button calls and adds exactly one thing to it: a `scope_key`.

⚠ **AND THAT ONE THING IS `P4.2`'s WHOLE OUTCOME, BECAUSE THE IDEMPOTENCY THE
BRIEF SAYS TO REUSE IS NOT SWITCHED ON TODAY.** The brief's words are *"Reuse
the idempotency the `jobs` table already has: one active job per tenant + kind
+ scope"*, and the constraint is real — `jobs.uq_jobs_active_scope`, a
`UniqueConstraint` over `(tenant, kind, scope_key)` conditioned on
`status IN ('queued','running') AND scope_key IS NOT NULL`. **MEASURED, by
reading `apps/tenancy/services.request_list_export`: it calls
`core_jobs.enqueue(...)` with a `payload` and NO `scope_key` at all.** The
condition on the partial index therefore excludes every list-export row ever
written, so the constraint is inert for exactly the job kind this module uses.
It is not broken and it was never wrong — a clerk pressing Export twice
deliberately WANTS two files. A schedule firing twice does not, and the
difference is entirely in whether a scope key is supplied. This module supplies
one; nothing about the clerk's path moves.

`scope_key` is `report_schedule:{schedule_id}:{due_instant}` — the schedule AND
the instant it was due, never just the schedule. Keying on the schedule alone
would make October's run fold into September's while September's was still
running, which is a lost report rather than a deduplicated one.

════════════════════════════════════════════════════════════════════════════
THE FOUR CADENCES, AND THE ONE THAT IS NOT A CRON EXPRESSION
════════════════════════════════════════════════════════════════════════════
`daily` · `weekly` · `monthly` · `monthly_on_cycle_close`. The first three are
ordinary calendar arithmetic against the PREVIOUS due instant, evaluated in the
tenant's own timezone (BR-TEN-081), and they are drawn as WORDS and never as a
cron string (p40 callout ①: *"'monthly, on cycle close', not `0 0 1 * *`"*).

⚠ **`monthly_on_cycle_close` RESOLVES TO THE TENANT'S ACCOUNTING-PERIOD CLOSE
DATE, AND THAT READING IS A LANE JUDGMENT RECORDED RATHER THAN A RULING** —
decision log 2026-09-27, and `OQ-REP-12741` is open for the PO to confirm the
word. The reasoning, written out because the next lane will otherwise re-derive
it and may land somewhere worse:

  · There are two things in this product that could be called a *cycle close*.
    One is the **accounting period's** close — `close_by`, COMPUTED by
    `apps.tenancy.selectors.current_period()` from the tenant's own fiscal
    settings under `BR-TEN-022`, ratified, already served, already on screen.
    The other is a **billing cycle** being finished.
  · **The second one is forbidden.** `CR-029 D8①` withdrew it on 2026-08-23 —
    PO verbatim, *"what makes a cycle completed - dont build it"*, `OQ-268`,
    **CLOSED — WITHDRAWN**. `apps/reports/dashboard_period.GAP_CYCLE_WINDOW_NOT_OFFERED`
    is the live refusal and says so in the tenant's own words. A lane deriving
    a billing-cycle close date here would be answering the exact question the
    PO declined, one module along.
  · So the only lawful reading is the first, and it needs nothing invented:
    `close_by` already exists, is already a date, and is already the date a
    finance officer means when they say *the books close*.

⚠ **WHEN `close_by` IS NULL THE SCHEDULE DOES NOT FIRE AND SAYS SO.** A tenant
with no fiscal calendar configured has no close date — `current_period()`
returns `None` outright without `fy_start_month`, and `_close_by_date` returns
`None` for an unparseable `close_day`. The honest answer is `next_run_at =
None` with the schedule left ENABLED, which screen `4·1` renders as **failing**
(p40 callout ③: *"a schedule whose report now errors stays in the list marked
failing and is not silently dropped"*). Substituting the 1st of the month would
be a number nobody chose, arriving on a date nobody expects, in a file a
finance officer would reconcile against.

════════════════════════════════════════════════════════════════════════════
TENANT CONTEXT, WHICH IS THE THING A SCHEDULER LOSES
════════════════════════════════════════════════════════════════════════════
`sweep_all_tenants` resolves the utilities through the RLS-EXEMPT registry
(`BR-TEN-003` — `tenants` is not a tenant-hosted table) and then enters
`core.tenancy.tenant_context(tenant_id)` before it touches a single
`report_schedules` row. `report_schedules` is RLS FORCE (reports `0005`), so a
bug in that loop reads nothing rather than reading somebody else's schedules.

⚠ **AND THE JOB BODY MUST NOT OPEN A SECOND ONE — `DEF-RBS-4363`, which this
module inherits the cure for rather than rediscovering.** `core.jobs.run_job`
has ALREADY entered the tenant context before it calls a handler, and
`core.tenancy.tenant_context` **clears on exit rather than restoring what it
replaced** (deliberately, so a job cannot carry one tenant's context into the
next iteration). A nested one therefore leaves NO tenant set when it returns,
and `run_job`'s very next statement reads the RLS-FORCEd `jobs` table and
raises *unknown job*. This module registers NO handler at all — it enqueues the
kind `apps/tenancy` already owns — so the trap is avoided by not being near it,
and this paragraph exists so nobody "tidies" a context in.

⚠ **THE DEFAULT SUITE CANNOT SEE ANY OF THIS.** `config/settings/test.py`
hardcodes in-memory SQLite, **which has no row-level security of any kind**, so
every assertion about the policy passes there by vacuum (hard-won law 14).
`tests/test_cr142_p4_schedules_pg.py` runs under `config.settings.local`
against real PostgreSQL 16 and is where the isolation claim is actually made.

════════════════════════════════════════════════════════════════════════════
RECIPIENTS — `P4.3`, AND WHY THE CHECK IS A REFUSAL AND NOT A FILTER
════════════════════════════════════════════════════════════════════════════
`BR-REP-020` is CONFIRMED: internal staff only. `resolve_recipients` takes the
ids a caller sent and answers the User rows for them — and **raises on anything
that is not a user of THIS tenant**, rather than quietly dropping it. A filter
would let a clerk pick three people, save, and find two on the schedule with
nothing on screen saying why; that is the silent half of hard-won law 2 and it
is worse here than a refusal, because the missing person is the one who was
supposed to receive the month-end pack.

⚠ **THERE IS NO EMAIL ARGUMENT ANYWHERE IN THIS MODULE, AND THAT IS THE
RULING.** The signature takes USER IDS. A free-text address cannot be
expressed, so W6's confirm step cannot be forgotten into existence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from core import jobs as core_jobs
from core import tenancy as core_tenancy
from apps.reports import report_seams
from apps.reports.models import (
    CADENCE_DAILY,
    CADENCE_MONTHLY,
    CADENCE_MONTHLY_ON_CYCLE_CLOSE,
    CADENCE_WEEKLY,
    CADENCES,
    ReportSchedule,
)

logger = logging.getLogger(__name__)

#: The job kind a schedule enqueues. ⚠ **THE PLATFORM'S OWN, NOT A NEW ONE** —
#: see the module docstring. `run_history.RUN_KINDS` reads the same string and
#: that is what puts a scheduled run on screen `5·1`.
SCHEDULE_JOB_KIND = "list_export"

#: The beat entry's name and its tick. One minute, matching
#: `apps/runbooks/scheduler.SWEEP_EVERY_SECONDS`, because the two sweeps answer
#: the same shape of question and a second cadence for the same job would be
#: two numbers to keep in step.
BEAT_ENTRY = "reports.schedule_sweep"
SWEEP_TASK = "smartbillhub.reports.schedule_sweep"
SWEEP_EVERY_SECONDS = 60

#: The hour, in the TENANT'S OWN timezone, at which a schedule fires.
#:
#: ⚠ **THE DRAWING NAMES NO TIME OF DAY AND THIS IS THEREFORE A CHOICE, MADE
#: ONCE AND WRITTEN DOWN.** Screen `4·1`'s *Next* column shows dates — *1 Oct*,
#: *29 Sep* — and never a clock. 06:00 local is the precedent `EP-RBS-03`
#: already set in this product (*"at 06:00 tenant local the sweep runs, and when
#: a clerk arrives the work list already holds…"*), and it is what makes the
#: phase's DONE WHEN true as written: a schedule set on Friday has produced its
#: file before anybody opens the product on Monday.
FIRE_AT_HOUR = 6

#: How far back the sweep will still fire a schedule it missed. A worker that
#: was down for an hour should still send the month-end pack; one that was down
#: for a week should not send six dailies at once.
#:
#: ⚠ **A MISSED FIRING IS FIRED ONCE, NEVER CAUGHT UP N TIMES.** `advance()`
#: walks `next_run_at` forward past every instant already gone, so a schedule
#: dormant for three days fires today and is next due tomorrow — it does not
#: emit three files. `BR-RBS-016` states the same posture for runbooks.
DUE_GRACE = timedelta(hours=24)


class RecipientError(ValueError):
    """A recipient that is not a user of this tenant. `P4.3` / `BR-REP-020`.

    A ValueError rather than a DRF exception so this module stays importable by
    the sweep, which has no request and no serializer behind it.
    """

    def __init__(self, unknown: Iterable[Any]) -> None:
        self.unknown = tuple(str(value) for value in unknown)
        super().__init__(
            "report schedule recipients must be users of this tenant: " + ", ".join(self.unknown)
        )


@dataclass(frozen=True)
class Recipient:
    """One internal staff member a schedule sends to.

    ⚠ **THE ID IS CARRIED AND THE NAME IS WHAT A SCREEN DRAWS** (B14 rule 31).
    `4·1`'s *Send to* column reads *"Dana W. +1"*; the uuid never reaches it.
    """

    user_id: str
    name: str
    email: str


# ═══════════════════════════════════════════════════════════════════════════
# RECIPIENTS — `P4.3`
# ═══════════════════════════════════════════════════════════════════════════


def tenant_staff(tenant_id: Any) -> tuple[Recipient, ...]:
    """The picker's options: every user of THIS tenant, and nobody else.

    ⚠ **SERVED, NEVER TYPED OUT ON THE FRONT END.** `SignupWizard.tsx` and
    `ratingShared.tsx` are this repo's worked case for a hand-typed list — an
    eleventh service existed, was served, and *"simply never appeared on the
    sign-up screen"*, silently, with every test green (B14 rule 2). A recipients
    picker with a hardcoded anything is the same defect aimed at a ruling.
    """
    found = report_seams.user_list(tenant_id)
    if found is None:  # pragma: no cover — identity is always published
        return ()
    # ⚠ **`found` YIELDS MEMBERSHIPS, SO THE PERSON IS `membership.user`.**
    # `identity.selectors.user_list` returns `TenantMembership` rows despite
    # its name; `report_seams.user_list`'s docstring records the measurement.
    # Reading `row.pk` here would carry the MEMBERSHIP's id into
    # `report_schedules.recipients`, and every id a screen sent back would then
    # be refused by the very rule this function exists to enforce.
    people = []
    for membership in found:
        user = getattr(membership, "user", None)
        if user is None:  # pragma: no cover — the join is select_related
            continue
        name = (getattr(user, "full_name", "") or "").strip()
        email = str(getattr(user, "email", "") or "")
        people.append(Recipient(user_id=str(user.pk), name=name or email, email=email))
    return tuple(people)


def resolve_recipients(tenant_id: Any, user_ids: Iterable[Any]) -> tuple[Recipient, ...]:
    """`BR-REP-020` — the ids, resolved, or a refusal naming what was refused.

    ⚠ **IT REFUSES; IT DOES NOT FILTER.** See the module docstring: a silently
    dropped recipient is a month-end pack that does not reach the person it was
    scheduled for, with nothing on any screen saying so.

    ⚠ **AND AN EMPTY LIST IS REFUSED TOO.** A schedule with no recipients
    produces a file and sends it nowhere — the run appears on `5·1` and nobody
    is told, which looks exactly like the product working. `2·3`'s *Send to* is
    a required field for this reason and not for tidiness.
    """
    wanted = [str(value) for value in user_ids if str(value).strip()]
    if not wanted:
        raise RecipientError(("<none>",))
    by_id = {person.user_id: person for person in tenant_staff(tenant_id)}
    unknown = [value for value in wanted if value not in by_id]
    if unknown:
        raise RecipientError(unknown)
    # De-duplicated, in the order the caller asked — the same person picked
    # twice is one recipient, and refusing that would be pedantry rather than
    # a rule.
    seen: list[str] = []
    for value in wanted:
        if value not in seen:
            seen.append(value)
    return tuple(by_id[value] for value in seen)


# ═══════════════════════════════════════════════════════════════════════════
# CADENCE ARITHMETIC — `P4.7`, four cases, four correct dates
# ═══════════════════════════════════════════════════════════════════════════


def tenant_zone() -> ZoneInfo:
    """The tenant's own timezone, or UTC. `BR-TEN-081`'s read, through a seam.

    UTC on an unconfigured tenant is `apps.tenancy.selectors.tenant_timezone`'s
    own fallback and is inherited rather than re-chosen here — two fallbacks for
    one fact is how two surfaces come to disagree about what day it is.
    """
    found = report_seams.tenant_timezone()
    return found if isinstance(found, ZoneInfo) else ZoneInfo("UTC")


def _at_fire_hour(day: date, zone: ZoneInfo) -> datetime:
    """`day` at `FIRE_AT_HOUR` local, as an aware instant.

    ⚠ **BUILT LOCAL AND THEN CONVERTED, NEVER THE OTHER WAY.** Adding a day to a
    UTC instant and calling it *tomorrow morning* is off by an hour twice a year
    in every North American timezone this product sells into — the DST fault
    `apps/runbooks/scheduler._to_instant` records in full.
    """
    return datetime.combine(day, time(hour=FIRE_AT_HOUR), tzinfo=zone)


def _add_months(anchor: date, months: int) -> date:
    """`anchor` + N months, CLAMPED into the target month.

    31 January + 1 month is 28 February (29 in a leap year), not 3 March.
    `apps.tenancy.selectors._add_months` is the same arithmetic and is private
    to that module; this is a deliberate second copy of six lines rather than a
    cross-module reach into a private name (B1).
    """
    index = anchor.month - 1 + months
    year = anchor.year + index // 12
    month = index % 12 + 1
    lengths = [31, 29 if _leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(anchor.day, lengths[month - 1]))


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _close_by(as_of: date) -> date | None:
    """The tenant's accounting-period close date, or None. See the docstring.

    ⚠ **READ THROUGH THE SEAM AND NEVER COMPUTED HERE.** `BR-TEN-022` makes the
    period a COMPUTED fact of the tenant's fiscal settings; a second derivation
    in this module would be a second answer to *when do the books close*, which
    is DEF-104's shape (four surfaces disagreeing about one balance).
    """
    period = report_seams.current_period(reference_date=as_of)
    if not isinstance(period, dict):
        return None
    raw = period.get("close_by")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:  # pragma: no cover — the seam serves ISO or nothing
        return None


def next_run_at(cadence: str, *, after: datetime, zone: ZoneInfo | None = None) -> datetime | None:
    """The NEXT instant this cadence is due, strictly after `after`.

    ⚠ **STRICTLY AFTER, WHICH IS WHAT STOPS A SCHEDULE FIRING TWICE FOR ONE
    DUE DATE.** `advance()` calls this with the instant that just fired; an
    inclusive comparison would hand the same instant back and the sweep would
    re-enqueue it a minute later. The `jobs` scope key would fold the second
    one, so the symptom would not be a duplicate file — it would be a schedule
    whose *Next* column never moved, which is harder to see and harder to
    explain.

    Returns `None` for `monthly_on_cycle_close` on a tenant with no accounting
    period configured. That is the refusal the module docstring describes and it
    is deliberately NOT a substituted date.
    """
    if cadence not in CADENCES:
        raise ValueError(f"unknown cadence: {cadence!r}")
    tz = zone or tenant_zone()
    local = after.astimezone(tz)
    today = local.date()
    # The same day's firing hour still counts when `after` is before it — a
    # schedule saved at 09:00 on Friday with a daily cadence is due Saturday,
    # but one saved at 02:00 is due the SAME morning, which is what a person
    # setting it at two in the morning means.
    if cadence == CADENCE_DAILY:
        candidate = _at_fire_hour(today, tz)
        return candidate if candidate > after else _at_fire_hour(today + timedelta(days=1), tz)
    if cadence == CADENCE_WEEKLY:
        candidate = _at_fire_hour(today, tz)
        if candidate > after:
            return candidate
        return _at_fire_hour(today + timedelta(days=7), tz)
    if cadence == CADENCE_MONTHLY:
        candidate = _at_fire_hour(today, tz)
        if candidate > after:
            return candidate
        return _at_fire_hour(_add_months(today, 1), tz)
    assert cadence == CADENCE_MONTHLY_ON_CYCLE_CLOSE  # the fourth and last
    close = _close_by(today)
    if close is None:
        return None
    candidate = _at_fire_hour(close, tz)
    if candidate > after:
        return candidate
    # This period's close has passed; ask the period that contains the day
    # after it, which is the next one.
    following = _close_by(close + timedelta(days=1))
    if following is None:
        return None
    candidate = _at_fire_hour(following, tz)
    return candidate if candidate > after else None


def advance(
    schedule: ReportSchedule, *, now: datetime, zone: ZoneInfo | None = None
) -> datetime | None:
    """Walk `next_run_at` forward past every instant already gone.

    ⚠ **ONE STEP PER CALL IS WRONG AND THE FIRST DRAFT DID IT.** A schedule
    whose worker was down for three days would then be due three days ago, fire,
    be due two days ago, fire again on the next tick — three files for one
    missed window. This loops until the answer is in the future, so a missed
    firing produces ONE run. `BR-RBS-016` is the same posture for runbooks:
    *"a missed firing raises rather than silently catching up"*.

    The loop is bounded: each iteration moves at least one day forward, and a
    cadence that cannot produce a later instant returns `None` and stops.
    """
    tz = zone or tenant_zone()
    cursor = schedule.next_run_at or now
    for _ in range(400):  # a year of dailies; a runaway is a bug, not a wait
        nxt = next_run_at(schedule.cadence, after=cursor, zone=tz)
        if nxt is None:
            return None
        if nxt > now:
            return nxt
        cursor = nxt
    return None  # pragma: no cover — unreachable for the four signed cadences


# ═══════════════════════════════════════════════════════════════════════════
# THE SWEEP — `P4.2`
# ═══════════════════════════════════════════════════════════════════════════


def scope_key(schedule_id: Any, due_at: datetime) -> str:
    """The idempotency key. Schedule AND instant — see the module docstring."""
    return f"report_schedule:{schedule_id}:{due_at.isoformat()}"


def due(*, now: datetime) -> list[ReportSchedule]:
    """Every enabled schedule of the CURRENT tenant that is due, oldest first.

    ⚠ **NO `.filter(tenant_id=…)` AND THAT IS NOT AN OVERSIGHT.**
    `report_schedules` is RLS FORCE and the caller has entered
    `tenant_context`; a belt-and-braces tenant filter here would make a missing
    context look like an empty result instead of like the bug it is. Hard rule
    1 is enforced by the database, and a second enforcement in Python is how a
    lane comes to believe the first one is optional.

    ⚠ **`next_run_at__isnull=False` IS LOAD-BEARING** — a NULL means paused or
    uncomputable (no accounting period), and `NULL <= now` is NULL rather than
    false, so a bare `lte` would already exclude it; the explicit clause is here
    so a reader does not have to know that about SQL three-valued logic.
    """
    horizon = now - DUE_GRACE
    return list(
        ReportSchedule.objects.filter(
            enabled=True,
            next_run_at__isnull=False,
            next_run_at__lte=now,
            next_run_at__gte=horizon,
        ).order_by("next_run_at")
    )


def fire(schedule: ReportSchedule, *, now: datetime, actor: Any = None) -> dict[str, Any] | None:
    """Enqueue ONE run for one schedule and move its next-run date on.

    Returns the job record, or `None` when the report could not be accepted.

    ⚠ **THE ADVANCE HAPPENS WHETHER OR NOT THE RUN SUCCEEDS.** A report that
    errors must not re-fire every minute until somebody notices; screen `4·1`
    marks the schedule **failing** from `last_job_id`'s job and the utility
    fixes it (p40 callout ③). Re-firing a broken report sixty times an hour is
    how a scheduler takes a product down.

    ⚠ **`last_job_id` IS SET EVEN ON A FAILURE TO ACCEPT — as `None`**, so the
    row cannot keep pointing at last month's successful job while this month's
    never started.

    ⚠⚠ **AND CLEARING IT DOES NOT PRODUCE THE SCREEN THIS DOCSTRING USED TO
    CLAIM — `DEF-REP-6929`, 2026-09-27.** It read *"…would render On in green
    over a report that has not run, which is hard-won law 2's mirror exactly"*,
    as though `None` were the cure. It is not: `schedules_api.status_of` calls
    `_job(None)`, which returns `None` meaning *we cannot say*, and that is
    rendered **`on`** — the very screen the sentence was warning about. A
    comment claiming a guarantee is not the guarantee (hard-won law 1), and
    this one was wrong about the file next door. **The accept-RAISES path is
    therefore still green-over-broken and is `DEF-REP-6929`, open.** The
    ordinary case — the job accepted and then FAILED — is unaffected and does
    read `failing`, because `last_job_id` points at the failed job.
    """
    due_at = schedule.next_run_at or now
    key = scope_key(schedule.pk, due_at)
    record: dict[str, Any] | None = None
    try:
        record = _enqueue(schedule, scope=key, actor=actor)
    except Exception:  # noqa: BLE001 — one broken schedule must not stop the sweep
        logger.exception(
            "report schedule %s could not be accepted; it is marked failing on 4·1 "
            "and its next run has still been advanced",
            schedule.pk,
        )
    schedule.last_job_id = record["id"] if record else None
    schedule.next_run_at = advance(schedule, now=now)
    schedule.save(update_fields=["last_job_id", "next_run_at", "updated_at"])
    return record


def _enqueue(schedule: ReportSchedule, *, scope: str, actor: Any) -> dict[str, Any]:
    """The accept call itself — the platform's, with a scope key added.

    ⚠ **THE PAYLOAD MIRRORS `request_list_export`'s FIELD FOR FIELD**, because
    `apps/tenancy/exports.run_list_export_job` reads those names and a schedule that
    invented its own spelling would produce a job the worker cannot run. The
    two additions are `scope_key` (the argument, not the payload) and
    `report_schedule_id`, which is what lets a support engineer answer *where
    did this file come from* from the job record alone.
    """
    params = dict(schedule.params or {})
    return core_jobs.enqueue(
        SCHEDULE_JOB_KIND,
        payload={
            "resource": str(params.get("resource") or ""),
            "q": str(params.get("q") or ""),
            "sort": params.get("sort"),
            "dir": params.get("dir"),
            "filters": dict(params.get("filters") or {}),
            "columns": list(params.get("columns") or []),
            "actor_user_id": str(schedule.created_by_user_id or "") or None,
            "report_schedule_id": str(schedule.pk),
        },
        scope_key=scope,
    )


def sweep(
    *,
    now: datetime | None = None,
    actor: Any = None,
    tenant_slug: str | None = None,
) -> dict[str, Any]:
    """Fire every due schedule of the CURRENT tenant, then DELIVER. Context must be set.

    ⚠ **THE SECOND HALF ARRIVED WITH `P4.10` (2026-09-27) AND IT IS THE
    PHASE'S DONE-WHEN.** Firing a schedule produces a file; the brief's
    sentence is *"delivered to named internal staff"*, and until that task
    this function stopped at the comma. `apps/reports/delivery.py` carries the
    whole argument for why delivery RECONCILES here rather than hooking the
    export job — the completion point belongs to the platform's export kernel,
    which is another module's file.

    ⚠ **DELIVERY IS FOR WHATEVER IS *READY* WHEN IT RUNS, AND THAT IS USUALLY
    NOT THE RUN THIS CALL JUST FIRED — BUT SOMETIMES IT IS, AND THE DIFFERENCE
    IS THE JOB TRANSPORT.** On a deployment the export is a Celery job, so a
    run accepted a millisecond ago has no file yet, `deliver_ready_runs` finds
    it *not ready*, and the NEXT tick — sixty seconds later — delivers it.
    **Under `JOBS_EAGER` the job finishes INSIDE `fire()`**, so the same call
    delivers it. Both are correct and neither is assumed: the only status that
    produces a message is the one screen `5·1` draws as *ready*, so an email
    can never announce a run that failed, whichever transport is in use.

    ⚠ **THIS PARAGRAPH SAID *NEVER* UNTIL ITS OWN TESTS SAID OTHERWISE
    (2026-09-27).** It read *"delivery is NOT for the runs this call just
    fired"* — a claim about a guarantee that the eager transport does not give,
    which is CLAUDE.md hard-won law 1 in the docstring of the function it is
    about. Five cases in `tests/test_cr142_p4_10_delivery.py` were written
    against the sentence and went red against the code; the code was right.

    `tenant_slug` is needed for the LINK and for nothing else. It is `None` for
    every caller that is not the beat, and a `None` slug produces no message
    rather than a broken address — see `delivery.NOT_DELIVERED_NO_TENANT_SLUG`.
    """
    moment = now or timezone.now()
    fired: list[str] = []
    for schedule in due(now=moment):
        with transaction.atomic():
            record = fire(schedule, now=moment, actor=actor)
        if record is not None:
            fired.append(str(record["id"]))
    # ⚠ LOCAL IMPORT, and it is not a style choice: `delivery` imports THIS
    # module for `resolve_recipients` and `RecipientError`, so a module-level
    # import here is a cycle whose behaviour depends on which of the two a
    # caller happens to import first.
    from apps.reports import delivery

    delivered = delivery.deliver_ready_runs(tenant_slug=tenant_slug, actor=actor)
    return {"fired": fired, "delivered": delivered["queued"], "delivery": delivered["outcomes"]}


def sweep_all_tenants() -> dict[str, Any]:
    """The beat body: every live utility, each in its own tenant context.

    ⚠ **A BROKEN TENANT MUST NOT STOP THE BEAT.** One utility whose fiscal
    settings are half-written cannot be allowed to hold up every other
    utility's month-end pack, so each tenant is swept inside its own try. A
    firing missed here is fired by the next tick — `DUE_GRACE` is 24 hours
    wide precisely so that is true.
    """
    try:
        listed = report_seams.live_tenants()
    except Exception:  # noqa: BLE001 — see above
        logger.exception(
            "the live-utility read could not be made, so no report schedule was "
            "swept this minute. Nothing is lost: the next tick fires it."
        )
        return {"tenants": 0, "fired": 0, "delivered": 0}

    tenants = 0
    fired = 0
    delivered = 0
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        try:
            with core_tenancy.tenant_context(tenant_id):
                # ⚠ THE SLUG IS PASSED DOWN AND NEVER RE-DERIVED. It is what
                # this loop already iterates, and `core.tenancy` publishes no
                # id → slug read; a link built without it would have a hole in
                # it. `P4.10`.
                outcome = sweep(tenant_slug=str(slug))
        except Exception:  # noqa: BLE001 — see above
            logger.exception("the report schedule sweep failed for %s", slug)
            continue
        tenants += 1
        fired += len(outcome["fired"])
        delivered += int(outcome.get("delivered") or 0)
    return {"tenants": tenants, "fired": fired, "delivered": delivered}


# ═══════════════════════════════════════════════════════════════════════════
# WIRING — the half that is not the schedule
# ═══════════════════════════════════════════════════════════════════════════

#: Bound by `install()`. Kept because `app.task(...)(fn)` returns a NEW object
#: and leaves the module-level name bound to the plain function, which has no
#: `.delay` — the trap `apps/notifications/schedule.py` records in full.
_SWEEP_TASK: Any = None


def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so a test can assert it
    without starting celery — *the schedule is correct* and *the schedule is
    installed* are two claims and hard-won law 2 is about exactly that gap.
    `apps/runbooks/scheduler.beat_schedule` is the same shape, deliberately.
    """
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(every_seconds if every_seconds is not None else SWEEP_EVERY_SECONDS),
            "args": (),
            "options": {"expires": SWEEP_EVERY_SECONDS * 5},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry and the sweep task. Idempotent.

    Called from `ReportsConfig.ready()`. Returns what it did, so a caller and a
    test can tell *installed* from *celery is not importable here* — the two
    look identical from outside and only one of them is a problem.

    ⚠ **A MISSING BROKER IS NOT AN ERROR.** `manage.py check`, every migration
    and the whole test suite run without one, and a product that refused to
    start because a scheduler was absent would be worse than one whose sweeps
    start a minute later.

    ⚠ **THE BRIEF SAYS `celery beat` IS NOT DEPLOYED TODAY AND THAT IS FALSE —
    MEASURED, AND IT IS WHY NO COMPOSE CHANGE SHIPS WITH THIS PHASE.**
    `P4.2`'s task line reads *"beat is NOT deployed today — celery itself is"*.
    `docker-compose.yml` carries a **`celery-beat` service**: its own
    `entrypoint: []`, `command: ["celery","-A","config.celery","beat",…]`,
    `replicas: 1`, and a margin note that was itself corrected on 2026-09-07
    for saying beat had nothing to fire. **THREE modules already install an
    entry from their own `AppConfig.ready()`** — `apps/notifications/schedule.py`,
    `apps/work/rules.py` and `apps/runbooks/scheduler.py` — and this is the
    fourth, by the same mechanism.

    ⚠ **SO A READER GREPPING `06-backend/config/` FOR A `beat_schedule` FINDS
    NOTHING AND MUST NOT CONCLUDE BEAT IS IDLE.** That absence is deliberate:
    each entry is registered by the module that owns the work, in the same
    `ready()` that registers its job body, because a schedule in one file and a
    body in another drift the first time either is renamed. `docker-compose.yml`
    says exactly this in its own margin, and the brief's sentence is almost
    certainly a grep for `beat_schedule` in `config/` read as evidence of
    absence — hard-won law 7's *reporting zero over a scope it silently
    excludes*.

    The consequence for this phase is the good one: **nothing about the
    deployment has to change.** Registering an entry nothing ticks would be a
    schedule that never fires with every test green, which is the shape
    `DEF-320` cost this product four job kinds of; that risk is not present
    here, and it was checked rather than assumed.
    """
    global _SWEEP_TASK
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the report schedule sweep was not installed: celery is not "
                "available here (%s). Nothing is broken — the sweep still runs "
                "when it is called.",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    _SWEEP_TASK = app.task(name=SWEEP_TASK, bind=False)(sweep_all_tenants)
    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


__all__ = [
    "BEAT_ENTRY",
    "DUE_GRACE",
    "FIRE_AT_HOUR",
    "SCHEDULE_JOB_KIND",
    "SWEEP_EVERY_SECONDS",
    "SWEEP_TASK",
    "Recipient",
    "RecipientError",
    "advance",
    "beat_schedule",
    "due",
    "fire",
    "install",
    "next_run_at",
    "resolve_recipients",
    "scope_key",
    "sweep",
    "sweep_all_tenants",
    "tenant_staff",
    "tenant_zone",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.2 · P4.3 · P4.7 (05-prototype/09 Reports Build Brief.pdf pp14–15, 34, 40, read as images per B14 rule 42)
# screens: 2·3 · 4·1 · 4·2
# generated: 2026-09-27 by lane REP-P4
# checklist: A✔ B=n/a(this file has no screen half — 2·3 and 4·1 are P4.4/P4.5) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr142_p4_schedules.py was run before this file existed and reported `ModuleNotFoundError: No module named 'apps.reports.schedules'`.
# exceptions: (1) `monthly_on_cycle_close` resolves to the ACCOUNTING-PERIOD close (BR-TEN-022 `close_by`) and not to a billing-cycle close, because CR-029 D8① withdrew the latter concept outright. LANE JUDGMENT, recorded in the decision log, with `OQ-REP-12741` open for the PO to confirm the word · (2) FIRE_AT_HOUR = 06:00 tenant-local is a CHOICE — the drawing names no time of day. Reported · (3) no job handler is registered here: this module enqueues the platform's own `list_export` kind so a scheduled run appears on `5·1` · (4) the brief's `P4.2` says celery beat is not deployed; MEASURED FALSE — `docker-compose.yml` runs a `celery-beat` service and three modules already install entries from `ready()`. No compose change ships. REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
