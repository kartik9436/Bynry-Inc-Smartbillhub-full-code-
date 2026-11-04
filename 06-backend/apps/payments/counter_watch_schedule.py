# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 task `P2.11` — the half that was REPORTED and not done.
#          `manage.py sweep_open_counters` and `apps/payments/counter_watch.py`
#          landed complete on 2026-09-23 and **nothing called either of them**
#          (`DEF-PAY-6268`).
# Rules:   PO ruling 2026-09-23 §3.1 (**no auto-close** — *"A System Admin
#          closes it. Dana cannot work Tuesday until someone is free to do
#          that"*, and, in the decision-log row that records it, *"no scheduled
#          job is written, so `P2.11`'s notice to the supervisor is **the only
#          thing that fires overnight** and it TELLS rather than CLOSES"*) ·
#          BR-TEN-081 (the utility's OWN clock decides what day it is) ·
#          BR-TEN-043 (beat owns a DURATION; the moment is NAMED by the caller)
#          · BR-TEN-013 / B1 (a module never touches another module's ORM;
#          tenancy is resolved BY NAME) · BR-NOT-009 (quiet hours — the
#          notifications layer, not this file, decides when a human is
#          disturbed) · CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is on)
#          · rule 6 (idempotency) · hard-won law 2 (built is not wired) ·
#          law 3 (the unsafe option is the one you type) · law 7
# Defects:  DEF-PAY-6268 (this gap) · DEF-3422 (a tenant list that was an unset
#          environment variable, so every firing reached nobody) · DEF-320 (a
#          queue nothing consumes — the same shape one layer down)
# Tests:   06-backend/tests/test_cr136_p2_11_schedule.py
# Impacts: apps/payments/apps.py (`ready()` installs the entry — THE line that
#          makes this real) · apps/payments/counter_watch.py (the sweep this
#          fires, unchanged except for its amended exception note) ·
#          apps/payments/management/commands/sweep_open_counters.py (the
#          by-hand path, unchanged and still the operator's) ·
#          10-scripts/gates/g132_beat_entries_are_installed.py ·
#          docker-compose.yml's `celery-beat` service (which fires it)
# ───────────────────────────────────────────────────────
"""The unclosed-till notice, once a morning, on each utility's OWN clock.

╔══════════════════════════════════════════════════════════════════════════╗
║  IT TELLS. IT NEVER CLOSES.                                             ║
║  PO ruling 2026-09-23 §3.1, verbatim:                                   ║
║  "(a) Your ruling stands — no auto-close. A System Admin closes it.     ║
║   Dana cannot work Tuesday until someone is free to do that"            ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
⚠ WHY THIS FILE IS NOT A BREACH OF THE RULING IT CITES — READ THIS FIRST
────────────────────────────────────────────────────────────────────────────
`CR-136-BRC07` §3.1 carries the bullet *"No scheduled job is written"*, and
`J-PAY-forgotten-till` reduced that to *"A scheduled job of any kind"* in its
list of things the journey deliberately does not contain. **Both are
paraphrases of the ruling and both are narrower than it**, which is what kept
this gap open for a day and is recorded as `DEF-PAY-6268`.

The RULING itself, in `12-governance/02-decision-log.md` at 2026-09-23, says in
one sentence what is forbidden and what is expected:

    "…only the midnight auto-close is struck; **no scheduled job is written**,
     so `P2.11`'s notice to the supervisor is **the only thing that fires
     overnight** and it TELLS rather than CLOSES…"

A notice that nothing schedules fires **never**, not overnight. What §3.1
forbids is a job that CLOSES A TILL; what it expects is exactly the thing this
file does. Nothing here writes to `counter_sessions`, `counter_watch.py`
contains no write at all, and a test asserts the absence in both files by
reading their source — because an absence is what no other check in this
repository can see.

────────────────────────────────────────────────────────────────────────────
WHAT WAS ACTUALLY WRONG, IN THE REPOSITORY'S OWN WORDS
────────────────────────────────────────────────────────────────────────────
`sweep_open_counters.py` said of itself: *"NOT SCHEDULED BY THIS LANE. This
repo carries no beat schedule to add it to."* The first half was true. **The
second half was false the day it was written** — five beat entries were already
installed from five `AppConfig.ready()` methods (`notifications.dispatch`,
`payments.collections_ladder`, `work.rules_sweep`, `runbooks.schedule_sweep`,
`customers.cut_date_watch`), the nearest of them in this very app. So the cost
the PO accepted — a clerk who cannot take money until somebody seals yesterday's
till — had no upper bound: nobody was told unless a person happened to type a
command.

────────────────────────────────────────────────────────────────────────────
⚠ THE BANKING DAY IS NOT THE SERVER'S MIDNIGHT, AND A CRON LINE CANNOT SAY SO
────────────────────────────────────────────────────────────────────────────
The notice's own drawn timing is *"When the banking day has ended"* (Settings →
Notifications, `notifications.rules.timing.end_of_banking_day`). A celery-beat
entry has ONE schedule for the whole deployment, and a utility in Houston and
one in Honolulu do not share a morning — they are four hours apart, and on the
day either of them changes offset they are five.

So this is a **SWEEP, not an alarm**, which is the shape
`apps/payments/collections_schedule.py` settled on one file over and the one
`09-infra/01-deployment-architecture.md` §10.3 tells the next lane to read
before adding another. Beat fires `watch_all` every
`COUNTER_WATCH_EVERY_SECONDS` (default 900 — a quarter hour), and each firing
asks each watched utility one question: **is it your hour yet, on your clock?**
Beat owns a DURATION; this file owns the per-utility DECISION. That division is
`BR-TEN-043`, and the interval is expressed in SECONDS because every installer
in this repo expresses its schedule that way and a mixed vocabulary in
`app.conf.beat_schedule` is how an entry gets read as the wrong unit.

The DAY comes from `apps.tenancy.selectors.tenant_today()` — BR-TEN-081's
published read half, the same one the command uses and the same one screen 3·1
reads — so the sweep and the screen cannot disagree about what day it is.
Nothing here re-derives it; a second copy of *"what day is it for this utility"*
is `DEF-094` rebuilt.

────────────────────────────────────────────────────────────────────────────
⚠ WHY 06:00 AND NOT MIDNIGHT — A JUDGMENT, AND THE ONE THING IT DOES NOT MOVE
────────────────────────────────────────────────────────────────────────────
**What counts as *left open* does not move and is not this file's to move.** A
till is left open when it was opened before the swept banking day began — the
cut-off is midnight of that day on the utility's own clock, it is a MOMENT
rather than a truncated `opened_at::date` (`OQ-153`), and `counter_watch.py`
argues it at length. This file decides only **when somebody is told**.

Three reasons the telling waits until the morning rather than firing at 00:0x:

  1. **`find_open_tills` was written for a morning sweep and says so.** It
     returns two figures, and the difference between them is *"somebody who
     closed late, this morning, before the sweep ran — a real and harmless
     thing that should not be reported as a problem."* Fire at five past
     midnight and that allowance can never fire: the clerk still cashing up at
     00:20 is reported, and a queued message cannot be recalled.
  2. **The message is for the person who can act on it, at the moment they
     can.** Nobody force-closes a till at 00:05. 06:00 on the utility's own
     clock is after the last clerk has gone home and before any counter opens,
     so the notice is waiting when a System Admin arrives and the till can be
     sealed before Dana needs one.
  3. **It costs nothing in urgency.** The whole outcome `P2.11` exists for is
     *"nobody has to notice a missing count by looking"*, and a supervisor
     reading it at 06:00 rather than 00:05 notices it just as early.

**It is an hour of the utility's own day, not of the server's**, so every
utility gets its own 06:00 — that is the whole multi-zone answer, and it is one
`COUNTER_WATCH_HOUR` applied through `settings_seam.tenant_timezone()` rather
than a per-tenant setting. There is no per-tenant hour BECAUSE THE BLUEPRINT
DRAWS NONE: §3.1 ruled that `Counter setup` ships with the float alone, and a
setting nothing draws is a surface this lane would be inventing. An operator
who wants another hour sets one environment variable for the deployment.

⚠ **A LATER SWEEP THAT DAY IS HARMLESS, WHICH IS WHY THE HOUR IS A CHOICE AND
NOT A CONSTRAINT.** `counter_watch.sweep_id` is a `uuid5` of the utility and the
day, so the first firing of a banking day queues the message and every later one
answers `counter_watch_summary_already_queued` (CLAUDE.md rule 6). Moving the
hour, or running the command by hand at 09:00, cannot produce a second message.

────────────────────────────────────────────────────────────────────────────
⚠ AND THE EMAIL IS NOT SENT BY THIS FILE, WHICH IS WHY IT NEED NOT WORRY
────────────────────────────────────────────────────────────────────────────
`counter_left_open` is an in-app AND email event. Queuing is not sending:
`apps/notifications/dispatcher.py` holds email and SMS outside each utility's
own send window (`BR-NOT-009`, `quiet_hours_start`/`quiet_hours_end`, in tenant
time). When a human is disturbed is that module's rule and not a scheduler's, so
nothing here tries to second-guess it.

────────────────────────────────────────────────────────────────────────────
⚠ WHO IT WATCHES, AND WHY THERE IS NO PER-UTILITY SWITCH
────────────────────────────────────────────────────────────────────────────
Every LIVE utility, through `apps.tenancy.selectors.live_tenant_subdomains` —
resolved BY NAME at call time, so no import statement binds payments to
tenancy's models (B1 / BR-TEN-013). `DEF-3422` is why this is not an environment
variable with an empty default: the notifications dispatcher paced
`NOTIFICATIONS_DISPATCH_TENANTS`, nothing anywhere set it, and **every firing on
every deployment dispatched to nobody** while the queue filled up behind it.
Watching no utility at all is the unsafe option (hard-won law 3), so it is not
what an unset variable means here. An operator who wants a subset names one in
`COUNTER_WATCH_TENANTS`.

There is **no per-utility on/off switch**, deliberately, and the reason is that
the utility already has one that a person can actually see: *Counter left open*
is a rule on Settings → Notifications, ON by default, and a utility may switch
it off there. `collections_schedule` has a switch because it WRITES to
customers; this only tells, and a second hidden switch would be a way of turning
a notice off that leaves the screen still saying it is on.

────────────────────────────────────────────────────────────────────────────
⚠ WOULD IT ACTUALLY FIRE? THE SAME TWO ANSWERS AS ITS FOUR SIBLINGS
────────────────────────────────────────────────────────────────────────────
**In `docker-compose.yml`: YES.** `celery-beat` imports Django, which runs every
`AppConfig.ready()`, which is where `install()` below is called — the identical
path `apps/notifications/schedule.py` proved end to end on 2026-08-29.

**On the host this product is deployed to: NO, and not because of anything
here.** `09-infra/01-deployment-architecture.md` §4.1 records that that host
carries a pre-existing `.env` and needs a reachable broker, at least one worker
and `JOBS_EAGER=false` done ON IT (hard-won law 4 — a template change never
reaches a host that already has a `.env`). Registering this entry does not
change that and does not claim to. **`watch_one()` is a plain function an
operator can call on any host**, and `manage.py sweep_open_counters` is
unchanged and still theirs.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from importlib import import_module
from typing import Any

logger = logging.getLogger("smartbillhub.payments.counter_watch_schedule")

#: The two routing names, pinned as LITERALS for `apps/tenancy/tasks.py`'s own
#: reason: *"a renamed task is a message nobody consumes, and the queue says
#: nothing about it."*
WATCH_TASK = "smartbillhub.payments.counter_watch"
FANOUT_TASK = "smartbillhub.payments.counter_watch_all"

#: The beat entry's own name. ONE key, so installing twice replaces rather than
#: duplicates — two entries would be two sweeps per interval. `G132` refuses two
#: modules sharing a key, which would be one schedule silently erasing another.
BEAT_ENTRY = "payments.counter_watch"

#: How often beat fires the sweep. SECONDS, because it is a DURATION and not a
#: time (BR-TEN-043) — see the module docstring for why an alarm cannot work.
#:
#: ⚠ **THE DEFAULT IS ALSO THE WIDTH OF THE FIRING WINDOW.** `watch_one` runs a
#: utility only in the FIRST sweep of its hour (`minute < the sweep in
#: minutes`), so that hour produces one pass rather than four. Set this to a
#: value that divides an hour; anything else still works — `sweep_id`'s
#: idempotency is what makes a repeat harmless — but it costs one extra indexed
#: query per utility per extra sweep.
DEFAULT_SWEEP_EVERY_SECONDS = 900
SWEEP_EVERY_SECONDS_ENV = "COUNTER_WATCH_EVERY_SECONDS"

#: The hour of the UTILITY'S OWN day a supervisor is told, 0–23. See the module
#: docstring for why it is 06:00 and not midnight, and for the one thing it does
#: NOT move (what counts as *left open*).
DEFAULT_WATCH_HOUR = 6
WATCH_HOUR_ENV = "COUNTER_WATCH_HOUR"

#: Comma-separated subdomains, when an operator wants a SUBSET. Unset means
#: every LIVE utility — see the module docstring for why the default is not `()`
#: (DEF-3422, hard-won law 3).
WATCH_TENANTS_ENV = "COUNTER_WATCH_TENANTS"

#: The registered task objects, bound by `install()`. ⚠ THE RESULT IS KEPT:
#: `app.task(...)(fn)` returns a NEW object and leaves the module-level name
#: bound to the plain function, which has no `.delay` — so a fan-out written as
#: `watch_one.delay` would run every utility's sweep INLINE inside beat's own
#: process, silently, with every test passing.
_WATCH_ONE_TASK: Any = None
_WATCH_ALL_TASK: Any = None

#: Carried on every report, exactly as `counter_watch.SweepResult` carries its
#: scope beside its result: a caller must never have to INFER an absence.
WATCH_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "watch_never_closes",
        "br_ref": "PO ruling 2026-09-23 §3.1",
        "detail": "this schedule tells a supervisor which counters were left open and "
        "closes none of them. A till is sealed by a System Admin's force close and by "
        "nothing else — the PO struck the blueprint's midnight auto-close and accepted "
        "the cost that a clerk cannot take money until somebody is free to do it.",
    },
    {
        "code": "watch_tells_the_bell_not_the_screen",
        "br_ref": "BR-NOT-009",
        "detail": "the message is queued, not sent. The notifications dispatcher holds "
        "email outside each utility's own send window, so a 06:00 sweep does not decide "
        "when a person is disturbed and does not try to.",
    },
)

#: What a firing says when tenancy can answer nothing. A sentence an operator can
#: act on, with no id and no code in it — B14 rule 32's posture, because it is
#: read by whoever is wondering why nobody was told.
NO_TENANTS_FOUND = (
    "No utility could be read, so no counters were looked at. Nothing is missed: the "
    "Counter screen still shows which tills are still open the moment a member of staff "
    "opens it, and the next firing tries again."
)


# ── configuration ─────────────────────────────────────────────────────────
def sweep_every_seconds() -> int:
    """The sweep interval, from configuration, with the default as the fallback.

    A value that is not a positive whole number is IGNORED with a log line
    rather than obeyed: a `0` or a `-1` would mean beat firing continuously,
    which is a loop and not a schedule.
    """
    raw = os.environ.get(SWEEP_EVERY_SECONDS_ENV, "").strip()
    if not raw:
        return DEFAULT_SWEEP_EVERY_SECONDS
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        logger.warning(
            "%s=%r is not a positive number of seconds — the counter watch is using its "
            "default of %s instead. A zero or negative interval is not a schedule.",
            SWEEP_EVERY_SECONDS_ENV,
            raw,
            DEFAULT_SWEEP_EVERY_SECONDS,
        )
        return DEFAULT_SWEEP_EVERY_SECONDS
    return seconds


def watch_hour() -> int:
    """The hour of each utility's OWN day the supervisor is told, 0–23.

    An unreadable or out-of-range value falls back to the default WITH A LOG
    LINE rather than refusing the tenant. That is the opposite direction from
    `collections_schedule.schedule_hour`, which raises — and the difference is
    the direction of the damage. A ladder run at an hour nobody chose posts
    certified disconnection notices; a notice read an hour early is read an hour
    early. Refusing here would mean a typo in an environment file silently
    switching the whole watch off, which is the failure this file exists to end.
    """
    raw = os.environ.get(WATCH_HOUR_ENV, "").strip()
    if not raw:
        return DEFAULT_WATCH_HOUR
    try:
        hour = int(raw)
    except ValueError:
        hour = -1
    if not 0 <= hour <= 23:
        logger.warning(
            "%s=%r is not an hour of the day — the counter watch is using its default "
            "of %s (on each utility's own clock) instead.",
            WATCH_HOUR_ENV,
            raw,
            DEFAULT_WATCH_HOUR,
        )
        return DEFAULT_WATCH_HOUR
    return hour


def configured_subdomains() -> tuple[str, ...]:
    """The utilities an OPERATOR named, in the order they wrote them.

    De-duplicated, because the same subdomain twice would be two sweeps per
    firing for one utility — harmless (`sweep_id`) and still pointless work.
    """
    raw = os.environ.get(WATCH_TENANTS_ENV, "")
    seen: list[str] = []
    for part in raw.split(","):
        subdomain = part.strip().lower()
        if subdomain and subdomain not in seen:
            seen.append(subdomain)
    return tuple(seen)


def _live_subdomains() -> tuple[str, ...]:
    """Every live utility, through tenancy's OWN published read.

    `BR-TEN-013` — resolved by NAME at call time, so no import statement binds
    this module to tenancy's models. A broken read must not stop the beat, so it
    is caught and reported rather than raised.
    """
    read = _resolve("tenancy", "live_tenant_subdomains")
    if read is None:  # pragma: no cover — published since DEF-3422
        return ()
    try:
        listed = read()
    except Exception:  # noqa: BLE001 — see the docstring
        logger.exception(
            "the live-utility read could not be made, so no counters were looked at. "
            "Nothing is lost — the Counter screen answers the same question on demand."
        )
        return ()
    seen: list[str] = []
    for entry in listed or ():
        subdomain = str(entry).strip().lower()
        if subdomain and subdomain not in seen:
            seen.append(subdomain)
    return tuple(seen)


def watched_subdomains() -> tuple[str, ...]:
    """The utilities this deployment watches. Configuration first, every live
    utility second — hard-won law 3, and `DEF-3422`'s lesson applied rather than
    repeated."""
    return configured_subdomains() or _live_subdomains()


# ── the beat entry ────────────────────────────────────────────────────────
def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so it can be asserted without
    starting celery — **and asserting THIS is not the check that matters.** The
    schedule being CORRECT and the schedule being INSTALLED are two different
    claims, hard-won law 2 is about exactly that gap, and `DEF-PAY-6268` is this
    feature having met it once already. The case that counts reads
    `config.celery.app.conf.beat_schedule`.
    """
    return {
        BEAT_ENTRY: {
            "task": FANOUT_TASK,
            "schedule": float(
                every_seconds if every_seconds is not None else sweep_every_seconds()
            ),
            "args": (),
            "options": {"expires": None},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the schedule and the two tasks on the celery app. Idempotent.

    Called from `PaymentsConfig.ready()`. Returns what it did, so a caller and a
    test can tell *installed* from *celery is not importable here* — the two look
    identical from outside and only one of them is a problem. A failure to import
    celery is NOT an error: `manage.py check`, a migration and the test suite all
    run without a broker, and a Django app that refused to boot without a
    scheduler would be a worse product than one whose notice goes out when the
    worker comes back.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the counter watch was not installed: celery is not available here (%s). "
                "Nothing is broken — the Counter screen still shows which tills are open, "
                "and `manage.py sweep_open_counters` still runs from a terminal.",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    global _WATCH_ONE_TASK, _WATCH_ALL_TASK
    _WATCH_ONE_TASK = app.task(name=WATCH_TASK, bind=False)(watch_one)
    _WATCH_ALL_TASK = app.task(name=FANOUT_TASK, bind=False)(watch_all)

    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


# ── the seam (resolved by NAME at call time, never imported — B1) ──────────
def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom every seam in payments uses, so no import
    statement binds this module to tenancy's internals and nothing here needs
    re-wiring when an owner moves a function.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover — tenancy ships in this repo
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _tenant_moment(zone: Any) -> dt.datetime:
    """ONE instant, in the utility's own zone. The only clock read in this file.

    ⚠ **A SCHEDULER CANNOT AVOID ASKING WHAT TIME IT IS — THAT IS WHAT A
    SCHEDULER IS** (`collections_schedule`'s words, and its `_tenant_moment` is
    the same call for the same reason). What it CAN avoid is asking twice: this
    instant decides the hour AND becomes the `finished_at` the sweep and the
    seam are handed, so nothing below this line reads a clock and every date
    remains an INPUT (BR-TEN-043). `G6` records the read; it is the fourth in
    `apps/payments/` and is declared in this file's lifecycle exceptions rather
    than left for a reader to find.
    """
    from django.utils import timezone as dj_timezone

    return dj_timezone.now().astimezone(zone)


def _next_run_at(moment: dt.datetime, hour: int) -> dt.datetime:
    """The next instant, in the utility's OWN zone, this watch would fire.

    A DERIVATION from the hour, not a stored fact, so it cannot go stale.
    """
    candidate = moment.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= moment:
        candidate = candidate + dt.timedelta(days=1)
    return candidate


def _sweep_minutes() -> int:
    """The sweep interval in whole minutes, at least 1 — the firing window."""
    return max(1, sweep_every_seconds() // 60)


# ── the sweep ─────────────────────────────────────────────────────────────
def watch_all() -> dict[str, Any]:
    """ONE firing: hand every watched utility its own turn.

    A fan-out and not a loop, for the reason notifications gives for its own:
    one utility's slow read must not delay another's. Beat discards the return
    value; it exists so a test and an operator running this by hand see the same
    facts.
    """
    subdomains = watched_subdomains()
    if not subdomains:
        logger.warning("the counter watch fired: %s", NO_TENANTS_FOUND)
        return {"tenants": [], "dispatched": 0, "problem": NO_TENANTS_FOUND}

    for subdomain in subdomains:
        try:
            if _WATCH_ONE_TASK is not None:
                _WATCH_ONE_TASK.delay(subdomain)
            else:
                # `install()` has not run (celery absent, or this was called by
                # hand). Read it inline rather than silently doing nothing — a
                # fan-out that dispatches nowhere and reports success is the
                # shape DEF-320 was.
                watch_one(subdomain)
        except Exception:  # noqa: BLE001 — one tenant's broker error is not all of them
            logger.exception(
                "could not hand %s its counter watch — its Counter screen still answers "
                "the same question on demand and nothing is lost",
                subdomain,
            )
    return {"tenants": list(subdomains), "dispatched": len(subdomains), "problem": None}


def watch_one(subdomain: str, *, force: bool = False) -> dict[str, Any]:
    """ONE utility's turn: tell a supervisor, if it is that utility's hour.

    Returns a plain dict of FACTS — what day it decided for, what it found, and
    every reason it did nothing — so the worker log, an operator running this by
    hand and a test all read the same thing.

    `force` skips the HOUR test and nothing else. It exists so an operator can
    run a utility's watch after a broker outage without waiting for tomorrow, and
    so a test can prove the rest of the path without freezing a clock. It cannot
    produce a second message: `sweep_id` is a `uuid5` of the utility and the day.

    ⚠ **IT CLOSES NOTHING.** Every line below either reads or hands the reading
    to `counter_watch.sweep`, which contains no write to `counter_sessions` at
    all. Both absences are asserted from the source in
    `tests/test_cr136_p2_11_schedule.py`, because an absence is the one thing no
    behavioural case can be relied on to notice.

    ⚠ **`tenant_context` CLEARS ON EXIT rather than restoring what was there
    before** (`core/tenancy.py` — a job's normal shape is to have no ambient
    context). A beat worker has none, but an operator or a test calling this
    from inside one does, so the caller's context is saved and put back: without
    that, every query after this call would be denied with nothing visibly
    wrong. `counter_watch.sweep` and `apps/audit/diagnostics.sweep_expired`
    record the same trap.
    """
    from core import tenancy as core_tenancy

    report: dict[str, Any] = {
        "subdomain": subdomain,
        "ran": False,
        "as_of": None,
        "reason": None,
        "tills_left_open": None,
        # Present from the start rather than added on success: a caller reading
        # `report["outcomes"]` must not have to know whether the sweep got far
        # enough to set it (a tenant that FAILED leaves `by_tenant` empty).
        "open_at_cutoff": None,
        "outcomes": [],
        "problems": [dict(problem) for problem in WATCH_UNAVAILABLE],
    }

    previous = core_tenancy.current_tenant_id()
    try:
        return _watch_one(report, subdomain, force=force)
    finally:
        if previous is not None:
            core_tenancy.set_current_tenant(previous)


def _watch_one(report: dict[str, Any], subdomain: str, *, force: bool) -> dict[str, Any]:
    """`watch_one`'s body, so its context save/restore reads as one statement."""
    from core import tenancy as core_tenancy

    lookup = _resolve("tenancy", "tenant_id_for_subdomain")
    if lookup is None:  # pragma: no cover — tenancy publishes it
        report["reason"] = "tenancy_lookup_unavailable"
        logger.error(
            "the counter watch cannot resolve %r: apps.tenancy.selectors."
            "tenant_id_for_subdomain is not published, so no utility can be entered.",
            subdomain,
        )
        return report

    tenant_id = lookup(subdomain)
    if tenant_id is None:
        report["reason"] = "unknown_tenant"
        logger.error(
            "the counter watch is configured for %r and no utility has that short web "
            "address. Its counters were not looked at; correct %s.",
            subdomain,
            WATCH_TENANTS_ENV,
        )
        return report

    # ⚠ **HARD RULE 1.** `counter_sessions` is under FORCE ROW LEVEL SECURITY
    # and a job has no ambient context, so a query made outside this block
    # matches zero rows and reports success — truthfully, about nothing.
    with core_tenancy.tenant_context(tenant_id):
        decided = _decide_within_tenant(report, force=force)
    if decided is None:
        return report

    day, cutoff, moment = decided
    # `counter_watch.sweep` enters the utility's context itself, exactly as the
    # command hands it triples from outside one. The day and the cut-off are
    # INPUTS by the time they get there (BR-TEN-043) and that module reads no
    # clock at all.
    from apps.payments import counter_watch

    result = counter_watch.sweep(
        [(tenant_id, cutoff, day)],
        finished_at=moment,
    )
    report["ran"] = True
    report["reason"] = None
    report["tills_left_open"] = result.tills_left_open
    report["tenants_examined"] = result.tenants_examined
    report["failed"] = dict(result.failed)
    for row in result.by_tenant:
        report["open_at_cutoff"] = row.open_at_cutoff
        report["outcomes"] = [dict(one) for one in row.outcomes]
    logger.info(
        "counter watch · %s · %s: %s counter(s) left open. Nothing was closed — a System "
        "Admin seals a till and a job never does (PO ruling 2026-09-23).",
        subdomain,
        day.isoformat(),
        result.tills_left_open,
    )
    return report


def _decide_within_tenant(
    report: dict[str, Any], *, force: bool
) -> tuple[dt.date, dt.datetime, dt.datetime] | None:
    """`(day, cutoff, moment)` when this utility should be swept, else None.

    Split out so the tenant context above reads as one statement and every early
    return below is inside it. Every refusal names itself in `report["reason"]`,
    so a firing that did nothing says WHICH nothing it did.
    """
    from apps.payments import settings_seam
    from apps.payments.exceptions import PaymentRuleError

    read = _resolve("tenancy", "tenant_today")
    if read is None:  # pragma: no cover — tenancy publishes it
        report["reason"] = "tenant_today_unavailable"
        return None
    today = read()
    if not isinstance(today, dt.date):  # pragma: no cover — defensive
        report["reason"] = "tenant_today_unavailable"
        return None

    try:
        zone = settings_seam.tenant_timezone()
    except PaymentRuleError as refusal:
        report["reason"] = "tenant_timezone_unavailable"
        report["detail"] = str(refusal)
        logger.error("the counter watch has no clock for %s: %s", report["subdomain"], refusal)
        return None

    moment = _tenant_moment(zone)
    if moment.date() != today:
        # Inside the midnight boundary: the instant this file read and the day
        # tenancy answered disagree. Sweeping under two opinions of what day it
        # is would take the cut-off from one and the hour from the other, which
        # is the bug BR-TEN-043 exists to prevent. The next sweep is unambiguous.
        report["reason"] = "midnight_boundary"
        report["as_of"] = today.isoformat()
        return None
    report["as_of"] = today.isoformat()

    hour = watch_hour()
    if not force:
        if moment.hour != hour:
            report["reason"] = "not_the_hour"
            report["next_run_at"] = _next_run_at(moment, hour).isoformat()
            return None
        # Only the FIRST sweep of the hour runs, so one hour is one pass rather
        # than one per sweep. `sweep_id` makes a repeat harmless either way; this
        # keeps it from costing an indexed query per utility per extra sweep.
        if moment.minute >= _sweep_minutes():
            report["reason"] = "already_swept_this_hour"
            return None

    # Midnight of the swept day ON THE UTILITY'S OWN CLOCK. A MOMENT, so nothing
    # here truncates a stored timestamp to a date (OQ-153). This is the cut-off
    # `counter_watch` documents and it is NOT this file's to move.
    cutoff = dt.datetime.combine(today, dt.time.min, tzinfo=zone)
    return today, cutoff, moment


def status() -> dict[str, Any]:
    """What can truthfully be said about this utility's counter watch.

    Called inside tenant context. Three facts from configuration — that the
    entry is registered, the hour on this utility's clock, and when it next runs
    — and no fourth. **When it LAST ran is absent rather than served as `null`**,
    because nothing in this product records a counter-watch pass and a screen
    would render a `null` as *"never"*, which is a claim and not an absence.
    """
    from apps.payments import settings_seam
    from apps.payments.exceptions import PaymentRuleError

    payload: dict[str, Any] = {
        "registered": _WATCH_ALL_TASK is not None,
        "sweep_every_seconds": sweep_every_seconds(),
        "hour": watch_hour(),
        "problems": [dict(problem) for problem in WATCH_UNAVAILABLE],
    }
    try:
        moment = _tenant_moment(settings_seam.tenant_timezone())
    except PaymentRuleError as refusal:
        payload["problems"].append(
            {
                "code": "counter_watch_clock_unreadable",
                "br_ref": "BR-TEN-081",
                "detail": str(refusal),
            }
        )
        return payload
    payload["next_run_at"] = _next_run_at(moment, payload["hour"]).isoformat()
    return payload


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-136-BRC07 §3.1 + task `P2.11` · 12-governance/02-decision-log.md 2026-09-23 (the ruling, and its own clause *"the only thing that fires overnight"*) · DEF-PAY-6268 · apps/payments/collections_schedule.py and apps/customers/disconnect_schedule.py (the two installers this follows rather than minting a third mechanism) · apps/payments/counter_watch.py (the sweep) · 09-infra/01-deployment-architecture.md §10.3
# generated: 2026-09-23 by lane P2-SCHEDULE
# checklist: A✔ B=deferred(no-API-half — a schedule is not a surface; what it finds is already served by `GET /counters`) C✔ D=deferred(as B) E=deferred(no-frontend-half — the message lands in the AppShell bell, which shipped with CR-009) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr136_p2_11_schedule.py · the beat entry was proved RED before green (hard-won law 7) through the harness that runs it: with `install()` removed from `PaymentsConfig.ready()`, `config.celery.app.conf.beat_schedule` held no `payments.counter_watch` key and G132 named the module in `run_gates`'s `run()`
# exceptions: (1) **IT CLOSES NOTHING.** No row of `counter_sessions` is created, updated or deleted by any path in this file or in `counter_watch.py`, and a test asserts the absence from the SOURCE of both. PO ruling 2026-09-23 §3.1.
#         (2) **ONE WALL-CLOCK READ, IN `_tenant_moment`, AND `G6` RECORDS IT.** A scheduler cannot avoid asking what time it is; `collections_schedule._tenant_moment` is the same read for the same reason, and the sweep needs a `finished_at` regardless. It is read ONCE and passed down, so every date below it is an INPUT (BR-TEN-043).
#         (3) **NO PER-UTILITY SWITCH**, deliberately — the utility's switch is the *Counter left open* rule on Settings → Notifications, which a person can see. A second hidden one would turn a notice off while the screen still said it was on.
#         (4) **NO PASS RECORD**, so `status()` can say when the watch NEXT runs and not when it last did. A table keyed on (utility, banking day) belongs with a screen that reads it, and a table with no reader is the built-not-wired shape this file exists to close. ⚠ **AND `status()` ITSELF HAS NO SCREEN READER TODAY** — said out loud rather than left to be found. It is for an operator and for the case that asserts what it refuses to claim; it renders nothing anywhere and promises nothing on a screen, which is why it is not hard-won law 2's shape. The day a Counter or Settings panel wants *when does this next run*, it is already the one answer.
#         (5) **IT DOES NOT FIRE ON THE DEPLOYED HOST** and this file does not claim it does — 09-infra §4.1's two `JOBS_EAGER` rows name the three things that host needs done ON IT (hard-won law 4).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
