# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-007 (EP-RBS-03) — CR-075 wave I tasks I1, I2 and I3.
#           I1 the two job kinds on the platform runner · I2 cron evaluated in
#           the TENANT's timezone · I3 a missed firing RAISES.
# Rules:    BR-RBS-016 (a schedule is evaluated in the tenant's timezone and a
#           missed firing raises rather than silently catching up) ·
#           BR-INT-054 as amended 2026-09-06 (the SCHEDULER is Runbooks'; the
#           queue and the worker are how work runs and stay with the platform) ·
#           BR-INT-062 (a wall-clock time that occurs twice runs ONCE — late is
#           a delay, twice is a duplicate) · BR-RBS-002 (a Check is constructed
#           with no writer, so a scheduled Check can write nothing) ·
#           BR-RBS-039 (every foreign read goes through this module's seams) ·
#           CLAUDE.md hard rule 1 (tenant context before any tenant table) ·
#           hard-won law 2 (built is not wired) · law 7 · law 14
# Tests:    06-backend/tests/test_us_rbs_007_scheduler.py ·
#           06-backend/tests/test_us_rbs_007_scheduler_pg.py ·
#           10-scripts/gates/g117_runbooks_queue_split.py
# Impacts:  apps/runbooks/apps.py (ready() calls register() and install()) ·
#           docker-compose.yml (`celery-runbooks`, `-Q runbooks` — the CONSUMER
#           half, in the same commit) · apps/runbooks/seams/tenancy_seam.py
#           (live_tenants(), the read this file needs and did not have) ·
#           apps/runbooks/services.py (`validated_cron` — cron refused at save)
# ───────────────────────────────────────────────────────
"""The product's first scheduler: a runbook fires on the utility's own clock.

WHAT THIS FILE IS FOR, IN ONE SENTENCE
--------------------------------------
`EP-RBS-03`'s exit test is *"nobody opens the product"* — at 06:00 tenant local
the sweep runs, and when a clerk arrives the work list already holds the
accounts that would have failed. Everything else in the module is something a
person presses. This is the file that presses it.

⚠ **THE SCHEDULER IS OURS AND THE QUEUE IS NOT** (`BR-INT-054` as amended
2026-09-06, PO verbatim: *"business logic , scheduling , processing we will take
it in run book"*). Deciding that *daily at 06:00* means the utility's own
morning, spreading tenants so three hundred of them do not fire in the same
second, and refusing to start a run that is still going are **scheduling**, and
they are here. How the work then RUNS — a broker, a queue, a worker — is the
platform's, and this module runs on it. That is why there is one scheduler in
this product and not two.

THREE THINGS IT DOES, AND THE THIRD IS THE ONE THAT IS EASY TO LEAVE OUT
------------------------------------------------------------------------
1. **I1 · TWO JOB KINDS ON THE PLATFORM RUNNER** — `runbooks.check` and
   `runbooks.act`, registered with `core.jobs` together with the queue they
   ride, in one statement, because the module that owns the work owns both
   halves. ⚠ **The execution plan said this task was ALREADY DONE and nothing
   implemented it** (`DEF-RBS-4353`): the two strings appeared in three
   documents and in zero Python files, while `apps/runbooks/apps.py`'s own
   `ready()` docstring said the opposite. It is done here.
2. **I2 · CRON IN THE TENANT'S TIMEZONE.** A weekly job at 07:00 UTC reaches a
   Texas utility at 01:00 or 02:00 depending on the month, and which of the two
   is a question nobody asked. Every fire time below is computed on the
   tenant's own wall clock through `zoneinfo` and converted to an instant once.
3. **I3 · A MISSED FIRING RAISES.** It appears in run history as **Failed**,
   naming the time it should have run. An absence is invisible to every check
   this repository has, and *"the sweep did not run for nine days"* is the kind
   of fact that is otherwise discovered by the bill run failing.

THE TWO DAYLIGHT-SAVING CASES, BOTH ANSWERED HERE
-------------------------------------------------
**The clock goes BACK and a wall time happens twice** (01:30 on the first Sunday
of November in Chicago). The runbook fires **ONCE**, on the first occurrence.
That is `BR-INT-062` — *late is a delay, twice is a duplicate* — and it falls
out of iterating the WALL CLOCK rather than the instant: 01:30 appears once in a
day's list of wall times however many instants map to it. `fold=0` picks the
first of the two.

**The clock goes FORWARD and a wall time never happens at all** (02:30 on the
second Sunday of March in Chicago). `EP-RBS-03` §8 records this case as
**unruled** and says it is ours to settle rather than the PO's. **It is settled
here: the runbook FIRES, LATE, ONCE** — at the instant the pre-transition clock
would have reached 02:30, which reads as 03:30 on the new clock. The decision
and its reasoning are in `12-governance/02-decision-log.md`, 2026-09-07.
**The alternative was to skip the day**, and skipping is the exact failure this
wave exists to prevent: a silent absence that no check in this repository can
see. A run an hour late is a fact a clerk can read on `RBS-008`; a run that
never happened is nothing at all. `TC-RBS-007.4` asserts it.

WHAT DECIDES WHETHER A FIRING IS *DUE* OR *MISSED*
--------------------------------------------------
One question and one grace window. The sweep computes every wall-clock firing
between an ANCHOR and now:

  * a firing within `DUE_GRACE_SECONDS` of now is **DUE** — it is enqueued;
  * a firing older than that is **MISSED** — it raises, once, as a `failed` run.

⚠ **THE ANCHOR IS DERIVED AND THERE IS NO `last_fired_at` COLUMN.** It is the
latest of: the last scheduled run's `started_at`, the moment the schedule was
last EDITED (`runbook_versions.summary` already records exactly which fields
moved, and that table is append-only), the runbook's own `created_at`, and
`now - MISS_LOOKBACK`. A column would have been a fifth place for the same fact
to be wrong in, and the append-only version history is a better record of *when
did this schedule start meaning this* than a column an edit would overwrite.

⚠ **THE FAILED RUN ROW IS ITSELF THE ANCHOR ADVANCE.** Its `started_at` is the
LATEST missed firing, so the next sweep computes firings after it and finds
none: the same window cannot raise twice. That is what *never six replays*
means in code rather than in prose.

⚠ **AND THE LOOK-BACK IS BOUNDED AND SAYS SO.** A runbook scheduled every hour
whose worker has been down for a fortnight would otherwise compute 336 missed
firings. The count stops at `MISS_LIMIT` and the sentence a clerk reads says
*"at least N"* rather than a number that is quietly a cap — law 7's rule that a
check which cannot cover its whole subject must print what it skipped.

WHY A DRY RUN IS THE DEFAULT AND WHY THAT IS NOT TIMIDITY
----------------------------------------------------------
`BR-RBS-004`: an Action always produces a plan first. A scheduled Action is
opened in `dry` unless the runbook carries `approved_up_front` (`BR-RBS-041`,
PO 2026-09-06), which is the ONE switch that removes the wait. A Check is
opened `dry` always and the word means nothing for it — it is constructed with
no writer at all (`BR-RBS-002`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.runbooks.scheduler")


# ═══════════════════════════════════════════════════════════════════════════
# I1 · THE TWO JOB KINDS AND THE QUEUE THEY RIDE
# ═══════════════════════════════════════════════════════════════════════════

#: `runbooks.check` — a Check on a schedule. It holds no writer whatever its
#: mode, so this kind can never reach a customer (`BR-RBS-002`).
CHECK_JOB = "runbooks.check"

#: `runbooks.act` — an Action on a schedule. It still produces a plan first
#: (`BR-RBS-004`); the gate decides whether it then waits (`BR-RBS-041`).
ACT_JOB = "runbooks.act"

JOB_KINDS: tuple[str, ...] = (CHECK_JOB, ACT_JOB)

#: ⚠ **BOTH HALVES OR NEITHER (`DEF-320`, and `G59`/`G80`/`G109` before this
#: one).** Routing a kind to a named queue that no worker drains produces a job
#: that is accepted, answers *queued*, and runs for ever. The consuming half is
#: `docker-compose.yml`'s `celery-runbooks` service running `-Q runbooks`, added
#: in the same commit as this constant, and the default worker stays `-Q celery`
#: so the split is real rather than cosmetic. `G117` refuses a tree with one
#: half and not the other.
#:
#: ⚠ **AND THE REASON IT IS ITS OWN QUEUE RATHER THAN THE DEFAULT ONE IS A
#: MEASURED NUMBER, NOT A PREFERENCE.** Wave `M` soaked the collections ladder
#: over 1,035 accounts in about 15 seconds with two per-account reads in the
#: path; the same shape over the top of the ICP — 40,000 accounts — extrapolates
#: to roughly ten minutes of worker time per firing. Ten minutes is survivable
#: for a weekly job and is not survivable on the queue a clerk's CSV export is
#: waiting on.
RUNBOOKS_QUEUE = "runbooks"

#: The beat entry's name, and the interval it fires on. One minute, because a
#: cron expression's finest grain is one minute: a coarser beat would make
#: *06:00* mean *some time in the next five minutes* and the screen would be
#: telling a clerk something slightly untrue.
BEAT_ENTRY = "runbooks.schedule_sweep"
SWEEP_EVERY_SECONDS = 60

#: A firing this recent is DUE; older than this it is MISSED. Fifteen minutes,
#: which is fourteen minutes of slack over the beat's own one-minute cadence —
#: a worker restart, a slow deploy or a beat that skipped a tick must not turn
#: a firing into a failure a clerk has to read.
DUE_GRACE_SECONDS = 900

#: How far back a missed firing is looked for at all, and how many are counted
#: before the sentence says *"at least"*.
MISS_LOOKBACK = timedelta(days=14)
MISS_LIMIT = 500


# ═══════════════════════════════════════════════════════════════════════════
# I2 · CRON, EVALUATED ON THE TENANT'S WALL CLOCK
# ═══════════════════════════════════════════════════════════════════════════


class CronError(ValueError):
    """A cron expression this scheduler cannot evaluate. Raised at SAVE."""


_FIELD_BOUNDS: tuple[tuple[str, int, int], ...] = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day of month", 1, 31),
    ("month", 1, 12),
    ("day of week", 0, 6),
)


@dataclass(frozen=True)
class CronSpec:
    """Five fields of a standard cron expression, each expanded to a set.

    ⚠ **DAY-OF-MONTH AND DAY-OF-WEEK ARE OR-ED WHEN BOTH ARE RESTRICTED**, which
    is standard cron and surprises everyone the first time. `0 6 1 * 1` is *the
    first of the month AND every Monday*, not *Mondays that fall on the first*.
    It is implemented that way because a utility copying a line out of its old
    system must get what that system did.
    """

    minutes: tuple[int, ...]
    hours: tuple[int, ...]
    days_of_month: tuple[int, ...]
    months: tuple[int, ...]
    days_of_week: tuple[int, ...]
    dom_restricted: bool
    dow_restricted: bool
    text: str

    def day_matches(self, day: date) -> bool:
        if day.month not in self.months:
            return False
        # Python's Monday=0; cron's Sunday=0. Convert once, here.
        dow = (day.weekday() + 1) % 7
        in_dom = day.day in self.days_of_month
        in_dow = dow in self.days_of_week
        if self.dom_restricted and self.dow_restricted:
            return in_dom or in_dow
        if self.dom_restricted:
            return in_dom
        if self.dow_restricted:
            return in_dow
        return True


def _expand(field: str, name: str, low: int, high: int) -> tuple[tuple[int, ...], bool]:
    """One cron field → the sorted values it names, and whether it restricts.

    Understands `*`, `n`, `a-b`, `*/s`, `a-b/s` and comma lists of those. It
    understands nothing else, and a `?`, an `L`, a `#` or a name (`MON`) is
    REFUSED by name rather than silently read as something else — a cron field
    misread is a job that runs at the wrong time for ever, and nothing on any
    screen would look wrong.
    """
    values: set[int] = set()
    restricted = False
    for part in field.split(","):
        piece = part.strip()
        if not piece:
            raise CronError(f"the {name} field of {field!r} has an empty item")
        step = 1
        if "/" in piece:
            piece, _, raw_step = piece.partition("/")
            piece = piece.strip()
            try:
                step = int(raw_step)
            except ValueError:
                raise CronError(f"the {name} step {raw_step!r} is not a whole number") from None
            if step < 1:
                raise CronError(f"the {name} step must be 1 or more, not {step}")
        if piece == "*":
            start, end = low, high
        elif "-" in piece:
            first, _, last = piece.partition("-")
            start, end = _one(first, name, low, high), _one(last, name, low, high)
            if start > end:
                raise CronError(f"the {name} range {piece!r} runs backwards")
            restricted = True
        else:
            start = end = _one(piece, name, low, high)
            restricted = True
        values.update(range(start, end + 1, step))
        if step > 1:
            restricted = True
    if not values:
        raise CronError(f"the {name} field {field!r} names no value")
    return tuple(sorted(values)), restricted


def _one(raw: str, name: str, low: int, high: int) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise CronError(
            f"the {name} value {raw.strip()!r} is not a whole number. This scheduler reads "
            f"five numeric fields — minute hour day-of-month month day-of-week — and nothing "
            f"else: no names, no L, no #, no ?."
        ) from None
    if not low <= value <= high:
        raise CronError(f"the {name} value {value} is outside {low}–{high}")
    return value


def parse_cron(text: str) -> CronSpec:
    """`"0 6 * * *"` → a `CronSpec`, or `CronError` naming the field.

    Called at SAVE as well as at fire time (`services._validated_setting`), so a
    schedule a clerk types wrong is refused while they are looking at it rather
    than at 06:00 on a morning when nobody is.
    """
    fields = (text or "").split()
    if len(fields) != 5:
        raise CronError(
            f"a cron expression has five fields — minute hour day-of-month month day-of-week — "
            f"and {text!r} has {len(fields)}"
        )
    minutes, _ = _expand(fields[0], *_FIELD_BOUNDS[0])
    hours, _ = _expand(fields[1], *_FIELD_BOUNDS[1])
    doms, dom_restricted = _expand(fields[2], *_FIELD_BOUNDS[2])
    months, _ = _expand(fields[3], *_FIELD_BOUNDS[3])
    dows, dow_restricted = _expand(fields[4], *_FIELD_BOUNDS[4])
    return CronSpec(
        minutes=minutes,
        hours=hours,
        days_of_month=doms,
        months=months,
        days_of_week=dows,
        dom_restricted=dom_restricted,
        dow_restricted=dow_restricted,
        text=" ".join(fields),
    )


def zone(name: str | None) -> ZoneInfo:
    """The tenant's own zone, or UTC — and an unknown name is refused, not guessed.

    ⚠ `DEF-MET-4101`'s root cause was *a clock question answered in the wrong
    frame*: every check compared UTC while the product showed local, so the two
    never met. Falling back to UTC on a typo would rebuild that defect one
    schedule at a time, so a name `zoneinfo` does not know raises here and the
    caller decides what to say.
    """
    text = (name or "").strip() or "UTC"
    try:
        return ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError) as problem:
        raise CronError(f"{text!r} is not a timezone this system knows") from problem


def _to_instant(naive_local: datetime, tz: ZoneInfo) -> datetime:
    """One wall-clock time in one zone → the UTC instant it happens at.

    Both daylight-saving cases resolve here and both are deliberate:

      * **AMBIGUOUS** (the clock went back; this wall time happens twice) —
        `fold=0` takes the FIRST occurrence, so the runbook runs ONCE.
        `BR-INT-062`: *late is a delay, twice is a duplicate*.
      * **NON-EXISTENT** (the clock went forward; this wall time never happens)
        — `fold=0` uses the offset in force BEFORE the transition, which lands
        the run on the first side of the gap: 02:30 in Chicago on a March
        Sunday becomes 08:30 UTC and reads as **03:30** on the new clock. **It
        runs, an hour late, once.** Skipping was the alternative and is the one
        thing this wave exists to prevent.
    """
    return naive_local.replace(tzinfo=tz).astimezone(dt_timezone.utc)


def local_wall_time_exists(naive_local: datetime, tz: ZoneInfo) -> bool:
    """Does this wall clock reading occur in this zone at all? (PEP 495.)

    Published rather than inlined because it is the only way to WRITE the
    spring-forward test: `_to_instant` deliberately returns an answer for a time
    that does not exist, so a test asserting *"it fires late"* needs an
    independent way to say the time was a gap.
    """
    instant = naive_local.replace(tzinfo=tz).astimezone(dt_timezone.utc)
    return instant.astimezone(tz).replace(tzinfo=None) == naive_local


def _local_days(spec: CronSpec, start: date, days: int) -> Iterator[date]:
    for offset in range(days + 1):
        day = start + timedelta(days=offset)
        if spec.day_matches(day):
            yield day


def fires_between(
    spec: CronSpec,
    tz: ZoneInfo,
    *,
    after: datetime,
    until: datetime,
    limit: int = MISS_LIMIT,
) -> list[datetime]:
    """Every firing strictly after `after` and at or before `until`, as instants.

    Both bounds are aware UTC datetimes; the walk itself is over the tenant's
    WALL CLOCK, which is the whole of `BR-RBS-016`. The list is ordered and
    capped at `limit` — a caller that gets `limit` entries back must say so
    rather than reporting the cap as a count.
    """
    if until <= after:
        return []
    span_days = (until - after).days + 2
    first_local = after.astimezone(tz).date()
    found: list[datetime] = []
    for day in _local_days(spec, first_local, span_days):
        for hour in spec.hours:
            for minute in spec.minutes:
                instant = _to_instant(datetime.combine(day, time(hour, minute)), tz)
                if instant <= after or instant > until:
                    continue
                found.append(instant)
                if len(found) >= limit:
                    return sorted(found)
    return sorted(found)


def next_fire_after(spec: CronSpec, tz: ZoneInfo, after: datetime, *, horizon_days: int = 400):
    """The next firing after `after`, or `None` inside `horizon_days`.

    `None` is a real answer rather than a failure: `0 6 30 2 *` — six o'clock on
    the thirtieth of February — parses, matches nothing, and a screen must be
    able to say *no next run* instead of drawing a date it invented.
    """
    first_local = after.astimezone(tz).date()
    for day in _local_days(spec, first_local, horizon_days):
        for hour in spec.hours:
            for minute in spec.minutes:
                instant = _to_instant(datetime.combine(day, time(hour, minute)), tz)
                if instant > after:
                    return instant
    return None


def next_run_at(runbook: Any, *, now: datetime | None = None) -> datetime | None:
    """`RBS-004` Overview's *next run* — the whole question, in one call.

    `None` when the runbook is disabled, is not on a schedule, has no cron, or
    has a cron that names no reachable date. A screen draws the absence; it
    never draws a guess.
    """
    if not getattr(runbook, "enabled", False):
        return None
    if getattr(runbook, "trigger_kind", None) != "schedule":
        return None
    raw = (getattr(runbook, "cron", None) or "").strip()
    if not raw:
        return None
    try:
        spec = parse_cron(raw)
        tz = zone(getattr(runbook, "timezone", None))
    except CronError:
        return None
    return next_fire_after(spec, tz, now or _utcnow())


def _utcnow() -> datetime:
    from django.utils import timezone as dj_timezone

    return dj_timezone.now()


# ═══════════════════════════════════════════════════════════════════════════
# I3 · THE SWEEP — WHAT IS DUE, AND WHAT WAS MISSED
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Verdict:
    """What one sweep decided about one runbook. Data, so a test can read it."""

    runbook_key: str
    due: datetime | None
    missed: tuple[datetime, ...]
    truncated: bool
    skipped_reason: str | None = None


def schedule_anchor(runbook: Any, *, now: datetime) -> datetime:
    """*Since when has this schedule meant what it means now?*

    The latest of four facts, every one of which is already durable:

      1. the last SCHEDULED run's `started_at` — including a `failed` row this
         sweep wrote for an earlier miss, which is what stops a window raising
         twice;
      2. the moment the schedule was last EDITED — read from
         `runbook_versions.summary`, which records the fields that moved and is
         append-only (`runbooks/0003`). A utility that changes *daily 06:00* to
         *weekly Monday* has not missed five firings of a schedule that no
         longer exists;
      3. the runbook's own `created_at`;
      4. `now - MISS_LOOKBACK`, so a runbook nobody has run since August does
         not produce a fortnight of history on the morning this ships.
    """
    from apps.runbooks import models

    candidates: list[datetime] = [now - MISS_LOOKBACK]
    created = getattr(runbook, "created_at", None)
    if created is not None:
        candidates.append(created)

    last = (
        models.RunbookRun.objects.filter(
            tenant_id=runbook.tenant_id,
            runbook_id=runbook.pk,
            trigger=models.TRIGGER_SCHEDULE,
        )
        .exclude(started_at=None)
        .order_by("-started_at")
        .values_list("started_at", flat=True)
        .first()
    )
    if last is not None:
        candidates.append(last)

    edited = _schedule_last_edited(runbook)
    if edited is not None:
        candidates.append(edited)
    return max(candidates)


#: The settings a change to which makes the schedule a DIFFERENT schedule. A cap
#: change is an edit and is not one of these — it does not move the clock.
_SCHEDULE_FIELDS = frozenset({"cron", "timezone", "trigger_kind", "enabled"})


def _schedule_last_edited(runbook: Any) -> datetime | None:
    from apps.runbooks import models

    rows = models.RunbookVersion.objects.filter(
        tenant_id=runbook.tenant_id, runbook_id=runbook.pk
    ).order_by("-version")[:50]
    for row in rows:
        for change in row.summary or ():
            if isinstance(change, dict) and change.get("field") in _SCHEDULE_FIELDS:
                return row.changed_at
    return None


def decide(runbook: Any, *, now: datetime) -> Verdict:
    """One runbook, one moment: what is due and what was missed.

    Pure apart from two reads, and it returns DATA rather than doing anything —
    so `TC-RBS-007.1` and `TC-RBS-007.2` can assert the decision on a tenant's
    wall clock without a broker, a worker or a job store anywhere near them.
    """
    key = getattr(runbook, "key", "?")
    raw = (getattr(runbook, "cron", None) or "").strip()
    if not raw:
        return Verdict(key, None, (), False, "no cron is set")
    try:
        spec = parse_cron(raw)
        tz = zone(getattr(runbook, "timezone", None))
    except CronError as problem:
        # A schedule that cannot be read is REPORTED, never silently skipped —
        # and it cannot normally exist, because `parse_cron` also runs at save.
        # A row predating that validation is exactly the case this catches.
        return Verdict(key, None, (), False, str(problem))

    anchor = schedule_anchor(runbook, now=now)
    fires = fires_between(spec, tz, after=anchor, until=now, limit=MISS_LIMIT)
    truncated = len(fires) >= MISS_LIMIT
    grace = timedelta(seconds=DUE_GRACE_SECONDS)
    due = [f for f in fires if now - f <= grace]
    missed = [f for f in fires if now - f > grace]
    return Verdict(key, due[-1] if due else None, tuple(missed), truncated)


def _missed_sentence(verdict: Verdict, tz: ZoneInfo) -> str:
    """What a clerk reads on `RBS-008` when a firing did not happen.

    Plain words, the tenant's own clock, and the ZONE NAMED — because *06:00* on
    a screen and *06:00* in a person's head have to be the same six o'clock
    (`BR-SHL-023`). No rule id and no internal code (B14 rule 32).
    """
    latest = verdict.missed[-1].astimezone(tz)
    stamp = latest.strftime("%-d %b %Y at %H:%M")
    zone_name = latest.tzname() or str(tz)
    if len(verdict.missed) == 1:
        return f"This runbook should have run on {stamp} {zone_name} and did not."
    earliest = verdict.missed[0].astimezone(tz).strftime("%-d %b %Y at %H:%M")
    count = f"at least {len(verdict.missed)}" if verdict.truncated else str(len(verdict.missed))
    return (
        f"This runbook should have run {count} times between {earliest} and "
        f"{stamp} {zone_name} and did not."
    )


def raise_missed(runbook: Any, verdict: Verdict) -> Any:
    """Write the **Failed** run a missed firing leaves behind — `BR-RBS-016`.

    ⚠ **ONE ROW FOR THE WHOLE WINDOW, NOT ONE PER MISSED FIRING.** *Never a
    silent catch-up and never six replays* cuts both ways: six rows would be six
    replays of the failure, and a clerk scrolling past six identical lines
    learns less than one line that says *nine times, between these two dates*.
    The row's `started_at` is the LATEST missed firing, which advances the
    anchor, so the same window can never raise twice.

    The row pins the runbook's CURRENT version. That is honest — the run did not
    happen, so no version produced it — and it keeps `RBS-008`'s version column
    from being the only null on the screen.
    """
    from apps.runbooks import models

    tz = zone(getattr(runbook, "timezone", None) or "UTC")
    text = _missed_sentence(verdict, tz)
    return models.RunbookRun.objects.create(
        tenant_id=runbook.tenant_id,
        runbook_id=runbook.pk,
        version=getattr(runbook, "current_version", 1) or 1,
        mode=models.MODE_DRY,
        trigger=models.TRIGGER_SCHEDULE,
        status=models.RUN_STATUS_FAILED,
        started_at=verdict.missed[-1],
        finished_at=_utcnow(),
        counts={"missed": len(verdict.missed)},
        report=[
            {
                "block": "sentence",
                "payload": {"tone": "danger", "label": "Missed", "text": text},
            }
        ],
    )


def scope_key(tenant_id: Any, runbook_key: str, fired_for: datetime) -> str:
    """One job per runbook per FIRING.

    `core.jobs.enqueue` folds a re-enqueue carrying a live scope key into the
    existing record (NFR-16), so a beat that ticks twice inside the grace window
    — a restart, a duplicated schedule, two beats during a deploy — becomes one
    job rather than two runs. The FIRING is in the key because tomorrow's 06:00
    is different work.
    """
    return f"{tenant_id}:{runbook_key}:{fired_for.astimezone(dt_timezone.utc).isoformat()}"


def _mode_for(runbook: Any) -> str:
    from apps.runbooks import models

    if runbook.kind == models.KIND_CHECK:
        return models.MODE_DRY
    if getattr(runbook, "gate_mode", None) == models.GATE_APPROVED_UP_FRONT:
        return models.MODE_LIVE
    return models.MODE_DRY


def _kind_for(runbook: Any) -> str:
    from apps.runbooks import models

    return CHECK_JOB if runbook.kind == models.KIND_CHECK else ACT_JOB


def sweep(*, now: datetime | None = None) -> dict[str, Any]:
    """ONE tenant's schedules, at one moment. The caller supplies the context.

    Returns what it did — enqueued, raised, skipped — because a sweep that
    reports nothing is a sweep nobody can tell apart from a sweep that ran over
    an empty list, and *"it fired for nobody"* is `DEF-3422` exactly.
    """
    from apps.runbooks import models

    moment = now or _utcnow()
    enqueued: list[str] = []
    raised: list[str] = []
    skipped: list[dict[str, str]] = []

    rows = models.Runbook.objects.filter(
        enabled=True, trigger_kind=models.TRIGGER_SCHEDULE
    ).exclude(cron=None)
    for runbook in rows:
        verdict = decide(runbook, now=moment)
        if verdict.skipped_reason:
            skipped.append({"runbook": verdict.runbook_key, "why": verdict.skipped_reason})
            continue
        if verdict.missed:
            raise_missed(runbook, verdict)
            raised.append(verdict.runbook_key)
        if verdict.due is None:
            continue
        record = core_jobs.enqueue(
            _kind_for(runbook),
            scope_key=scope_key(runbook.tenant_id, runbook.key, verdict.due),
            payload={
                "tenant_id": str(runbook.tenant_id),
                "runbook_key": runbook.key,
                "mode": _mode_for(runbook),
                "fired_for": verdict.due.astimezone(dt_timezone.utc).isoformat(),
            },
        )
        enqueued.append(str(record["id"]))
    return {"enqueued": enqueued, "raised": raised, "skipped": skipped}


def sweep_all_tenants() -> dict[str, Any]:
    """ONE beat firing: sweep every live utility, each in its own context.

    A loop over tenants rather than a fan-out of jobs, because the sweep itself
    is two indexed reads per scheduled runbook and the WORK it finds is what
    goes on the queue. Fanning the sweep out would put a job on the queue to
    decide whether to put a job on the queue.

    ⚠ **A BROKEN TENANT MUST NOT STOP THE BEAT.** One utility with an
    unreadable schedule cannot cost every other utility its morning, so each is
    swept inside its own `try`. The failure is logged with the subdomain, which
    is the thing an operator can act on.
    """
    from apps.runbooks.seams import tenancy_seam

    try:
        listed = tenancy_seam.live_tenants()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception(
            "the live-utility read could not be made, so no schedule was swept this "
            "minute. Nothing is lost: a firing missed here is raised by the next sweep."
        )
        return {"tenants": 0, "enqueued": 0, "raised": 0}

    tenants = 0
    enqueued = 0
    raised = 0
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        try:
            with core_tenancy.tenant_context(tenant_id):
                outcome = sweep()
        except Exception:  # noqa: BLE001 — see the docstring
            logger.exception("the schedule sweep failed for %s", slug)
            continue
        tenants += 1
        enqueued += len(outcome["enqueued"])
        raised += len(outcome["raised"])
    return {"tenants": tenants, "enqueued": enqueued, "raised": raised}


# ═══════════════════════════════════════════════════════════════════════════
# THE JOB BODY — WHAT THE WORKER ACTUALLY RUNS
# ═══════════════════════════════════════════════════════════════════════════


def run_scheduled_job(record: dict[str, Any]) -> str | None:
    """`runbooks.check` and `runbooks.act` share one body, and that is correct.

    The two kinds exist so the QUEUE and a reader can tell a Check from an
    Action — a Check writes nothing and an Action may — and not because the two
    do different things here. `services.run_to_completion` already takes the
    mode, refuses a live run the trust ratchet holds (`BR-RBS-036`), and refuses
    a run whose stored version and live module have diverged (`BR-RBS-038`).
    A second body would be a second place for those refusals to be forgotten.

    ⚠ **IT DOES NOT OPEN A TENANT CONTEXT, AND THE FIRST DRAFT DID — WHICH IS
    `DEF-RBS-4363`, FOUND BY THE WALKTHROUGH AND BY NOTHING ELSE.**
    `core.jobs.run_job` has already entered `tenant_context(record["tenant_id"])`
    before it calls this function, and `core.tenancy.tenant_context` **CLEARS on
    exit rather than restoring what it replaced** — deliberately, so a job can
    never carry one tenant's context into the next tenant's loop iteration. So a
    nested one leaves NO tenant set when this returns, and `run_job`'s very next
    statement is `succeed(job_id)` → `_load(job_id)`, which reads the RLS-FORCEd
    `jobs` table, finds nothing and raises *unknown job*. **The RUN is written
    correctly and only the JOB record says failed**, which no screen reads yet.
    ⚠ **AND THE DEFAULT SUITE CANNOT SEE IT AT ALL** — `config/settings/test.py`
    hardcodes SQLite, which has no row-level security, so the missing tenant
    reads every row and the job succeeds. That is hard-won law 14's shape one
    layer up, which is why the test asserts *the context is still set when this
    returns* rather than asserting the job succeeded: that assertion fails on
    SQLite too. `apps/billing/run_jobs.py` and `apps/metering/import_runs.py`
    are the correct precedent; `apps/work/rules.py`'s `run_rules_sweep_job` has
    the identical nesting and is reported in `DEF-RBS-4363` rather than changed
    from here.
    """
    from apps.runbooks import selectors, services
    from apps.runbooks.registry import registry

    payload = dict(record.get("payload") or {})
    tenant_id = record.get("tenant_id") or payload.get("tenant_id")
    key = str(payload.get("runbook_key") or "")
    runbook = selectors.runbook_by_key(tenant_id, key)
    if runbook is None:
        # A runbook deleted between the enqueue and the worker. Not an error:
        # the schedule is gone, so the work is gone with it.
        return None
    definition = registry.get(runbook.template_key or runbook.key)
    # ⚠ `CR-173-BRC10` — A RUN A PERSON STARTED RIDES THE SAME BODY. The two
    # job kinds were written for the schedule, and `POST /runbooks/{key}/runs`
    # (`services.request_run`) enqueues the same kinds with `trigger=manual`
    # and the person's one-off inputs. A schedule's payload carries neither,
    # so it reads exactly as before: trigger `schedule`, no overrides.
    from apps.runbooks import models as runbook_models

    trigger = str(payload.get("trigger") or runbook_models.TRIGGER_SCHEDULE)
    if trigger not in (runbook_models.TRIGGER_MANUAL, runbook_models.TRIGGER_SCHEDULE):
        trigger = runbook_models.TRIGGER_SCHEDULE
    run, _result = services.run_to_completion(
        runbook,
        definition,
        mode=str(payload.get("mode") or "dry"),
        trigger=trigger,
        params=dict(payload.get("params") or {}) or None,
    )
    return f"/api/runbooks/runs/{run.pk}"


def register() -> None:
    """Register the two bodies AND the queue they ride — both, here, together.

    `core/jobs.py`'s contract is that the module owning the work owns both
    halves, and the reason is drift: a kind registered in one file and routed in
    another keeps its old queue after a rename, silently. `apps/work/rules.py`
    and `apps/integrations/jobs.py` say the same in their own words.
    """
    for kind in JOB_KINDS:
        core_jobs.set_job_handler(kind, run_scheduled_job)
        core_jobs.set_job_queue(kind, RUNBOOKS_QUEUE)


def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so a test can assert it
    without starting celery — *the schedule is correct* and *the schedule is
    installed* are two claims and hard-won law 2 is about exactly that gap.
    `apps/work/rules.py` and `apps/notifications/schedule.py` are the same
    shape, deliberately.
    """
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(
                every_seconds if every_seconds is not None else SWEEP_EVERY_SECONDS
            ),
            "args": (),
            "options": {"expires": SWEEP_EVERY_SECONDS * 5},
        }
    }


#: The routing name, pinned as a literal for the reason `apps/tenancy/tasks.py`
#: gives for its own: a renamed task is a message nobody consumes, and the queue
#: says nothing about it.
SWEEP_TASK = "smartbillhub.runbooks.schedule_sweep"

#: Bound by `install()`. Kept because `app.task(...)(fn)` returns a NEW object
#: and leaves the module-level name bound to the plain function, which has no
#: `.delay` — the trap `apps/notifications/schedule.py` records in full.
_SWEEP_TASK: Any = None


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry and the sweep task. Idempotent.

    Called from `RunbooksConfig.ready()`. Returns what it did, so a caller and a
    test can tell *installed* from *celery is not importable here* — the two
    look identical from outside and only one of them is a problem. A missing
    broker is NOT an error: `manage.py check`, every migration and the whole
    test suite run without one, and a product that refused to start because a
    scheduler was absent would be worse than one whose sweeps start a minute
    later.
    """
    global _SWEEP_TASK
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the runbooks schedule sweep was not installed: celery is not "
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
    "ACT_JOB",
    "BEAT_ENTRY",
    "CHECK_JOB",
    "CronError",
    "CronSpec",
    "DUE_GRACE_SECONDS",
    "JOB_KINDS",
    "MISS_LIMIT",
    "MISS_LOOKBACK",
    "RUNBOOKS_QUEUE",
    "SWEEP_EVERY_SECONDS",
    "SWEEP_TASK",
    "Verdict",
    "beat_schedule",
    "decide",
    "fires_between",
    "install",
    "local_wall_time_exists",
    "next_fire_after",
    "next_run_at",
    "parse_cron",
    "raise_missed",
    "register",
    "run_scheduled_job",
    "schedule_anchor",
    "scope_key",
    "sweep",
    "sweep_all_tenants",
    "zone",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-007 (EP-RBS-03 §"Scheduling" + BR-RBS-016 verbatim) · CR-075 wave I tasks I1, I2, I3 · BR-INT-054 as amended 2026-09-06 · BR-INT-062 (the fall-back case)
# generated: 2026-09-07 by the CR-075 wave I build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own — the sweep is a beat entry, and next-run rides GET /runbooks/{key}) E✔(RBS-008 run history and RBS-004's next-run line) F✔ G✔ H=n/a(no 🔒 path — no migration, no money, no idempotency key of the ledger's kind)
# gates: pytest tests/test_us_rbs_007_scheduler.py · pytest tests/test_us_rbs_007_scheduler_pg.py · G117 (the runbooks queue split, shown RED first through run_gates.py) · G115 (the import census)
# exceptions: the spring-forward case (a wall time that never occurs) is settled by THIS LANE — it fires late, once — and recorded in 12-governance/02-decision-log.md 2026-09-07 rather than put to the PO, because EP-RBS-03 §8 says the case is ours; the FALL-BACK case is BR-INT-062's and is only implemented here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
