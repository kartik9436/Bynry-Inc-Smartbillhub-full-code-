# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-030 (S90 · DSC-02) — the disconnect register and its cases.
# Change:   PO 2026-09-20, verbatim: *"Something has to read cut dates daily and
#           surface what's due… A case due last week stops looking identical to
#           one due next month. The clerk stops being the scheduler."*
#           This is the JOB half; the screen half is the register's DUE NOW view
#           (`07-frontend/src/features/customers/DisconnectsTab.tsx`).
# Rules:    BR-TEN-043 (the moment is NAMED by the caller — beat owns a
#           DURATION, this file owns no clock) · BR-TEN-081 (the utility's own
#           business day decides what *today* is) · BR-TEN-013 / B1 (a module
#           never touches another module's ORM; tenancy is resolved BY NAME) ·
#           CLAUDE.md hard rule 1 (tenant scoping — every read is inside
#           `tenant_context`) · hard-won law 2 (built is not wired) · law 3 (the
#           unsafe option is the one you type) · law 7 (print what was skipped
#           beside what was checked)
# Defects:  DEF-320 (the deployed shape of *"nothing reads a date"* — fixed for
#           the broker on 2026-08-19; this closes the disconnect half of the
#           sentence `disconnects.NO_SCHEDULER` has carried since 2026-08-25)
# Tests:    06-backend/tests/test_w7_worklists.py :: test_dsc_every_kpi_tile_equals_the_rows_of_its_own_segment (EXTENDED, not a second check) · 10-scripts/po20260921_cut_date_watch_walkthrough.mjs
# Impacts:  apps/customers/apps.py (`ready()` installs the entry) ·
#           apps/customers/disconnect_due.py (the ONE predicate it reads) ·
#           apps/customers/disconnects.py (`NO_SCHEDULER` amended, dated) ·
#           docker-compose.yml's `celery-beat` service (which fires it)
# ───────────────────────────────────────────────────────
"""The cut-date watch — something reads cut dates daily, and cuts nothing.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE GAP THIS CLOSES, IN THE REPOSITORY'S OWN WORDS.                    ║
╚══════════════════════════════════════════════════════════════════════════╝
`disconnects.NO_SCHEDULER` has ridden on **every ladder answer this product has
ever served**, and the Accounts blueprint prints the same sentence in red beside
the case record on p139:

    "Nothing performs that cut on the day. No runner, job, queue or timer in
     this product reads a date and acts on it."

`disconnect_cases.cut_scheduled_for` carries its own note in the model —
*"A STORED DATE THAT NOTHING WATCHES"* — and the completion code has exactly one
caller: a person pressing **Mark as cut**. So a cut booked for last Monday and
one booked for next month were the same row, and the clerk was the scheduler.

────────────────────────────────────────────────────────────────────────────
⛔ THIS DOES NOT CUT ANYTHING, AND THAT IS THE DESIGN RATHER THAN A STAGE
────────────────────────────────────────────────────────────────────────────
**Nothing in this file writes a row.** It reads `disconnect_due.due_register`,
logs what it found and returns it. It does not commit a cut, advance a tier,
write a notice, queue a message or move a case out of its state.

That is deliberate and it is the whole of the approval: the PO asked for the due
work to be **surfaced**, not executed. Nothing in this product has ever taken a
supply off a household without a person pressing a button, and a schedule that
started doing so would be a change to a utility's practice made by a deploy —
the exact hazard `payments/collections_schedule.py` names as its reason for
shipping switched OFF.

Whether an unattended job may EVER perform a cut is **`OQ-CUS-12525`, OPEN**. It
is a question and not an inference, and a lane that reads a schedule existing as
permission to act on it has resolved an open question by choosing a value.

⚠ **BECAUSE IT WRITES NOTHING, IT NEEDS NO IDEMPOTENCY GUARD, AND THAT IS
WORTH STATING RATHER THAN LEAVING AS AN ABSENCE (law 1).** `collections_
schedule` runs a tenant only in the first sweep of its configured hour, and
`work.rules_sweep` folds a repeat onto a `scope_key`, because both of them
WRITE. A second firing of this watch on the same day costs one log line and
produces the identical report. There is no same-day guard here because there is
nothing for one to protect.

────────────────────────────────────────────────────────────────────────────
⚠ WHO IT WATCHES, AND WHY THAT IS A READ RATHER THAN A VARIABLE
────────────────────────────────────────────────────────────────────────────
Every LIVE utility, through `apps.tenancy.selectors.live_tenant_subdomains` —
resolved BY NAME at call time, so no import statement binds customers to
tenancy's models (B1 / BR-TEN-013).

`DEF-3422` is why this is not an environment variable. The notifications
dispatcher paced `NOTIFICATIONS_DISPATCH_TENANTS`, nothing anywhere set it, and
**every firing on every deployment dispatched to nobody** while the queue filled
up correctly behind it. Hard-won law 3: watching no utility at all is the unsafe
option, so it is not what an unset variable means here. An operator who wants a
subset names one in `DISCONNECT_WATCH_TENANTS` and gets exactly that.

────────────────────────────────────────────────────────────────────────────
⚠ WHAT IT CANNOT DO, COUNTED (hard-won law 7)
────────────────────────────────────────────────────────────────────────────
**It reaches a clerk who opens the register, and nobody else.** The report is a
log line and a return value; the SURFACE is the DUE NOW view on S90, which reads
the same predicate. There is no bell message, and that is not an oversight:
`notifications.bulk_summary.queue_staff_alert` is the only staff entry point
this product has, it **refuses a `failed_count` below 1**, and it addresses
every System Admin under `BR-NOT-021` because it treats every alert as a
FAILURE. *"Three cuts are due today"* is not a failure, and writing it through
that door would put `total 3 · failed 3` in a clerk's inbox. Which event class a
due cut belongs to and who should be told is a ruling — **`OQ-CUS-12526`,
OPEN** — and this module states the absence rather than inventing an audience.

**`closed_out` cases are counted as overdue and how many there are is not
measured** — `disconnect_due.CLOSED_OUT_COUNT_UNKNOWN`, tracking
`DEF-CUS-5777`. It travels on every report.

────────────────────────────────────────────────────────────────────────────
⚠ WOULD IT ACTUALLY FIRE? THE SAME TWO ANSWERS AS THE LADDER'S
────────────────────────────────────────────────────────────────────────────
**In `docker-compose.yml`: YES.** `celery-beat` imports Django, which runs every
`AppConfig.ready()`, which is where `install()` below is called — the identical
path `apps/notifications/schedule.py` proved end to end on 2026-08-29.

**On the host this product is deployed to: NO, and not because of anything
here.** `09-infra/01-deployment-architecture.md` §4.1 records that that host
carries a pre-existing `.env` and needs a reachable broker, at least one worker
and `JOBS_EAGER=false` done ON IT (hard-won law 4). Registering this entry does
not change that and does not claim to. **`watch_one()` is a plain function an
operator can call on any host**, which is what makes this useful before that day
rather than after it.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from importlib import import_module
from typing import Any

logger = logging.getLogger("smartbillhub.customers.disconnect_schedule")

#: The two routing names, pinned as LITERALS for `apps/tenancy/tasks.py`'s own
#: reason: *"a renamed task is a message nobody consumes, and the queue says
#: nothing about it."*
WATCH_TASK = "smartbillhub.customers.cut_date_watch"
FANOUT_TASK = "smartbillhub.customers.cut_date_watch_all"

#: The beat entry's own name. ONE key, so installing twice replaces rather than
#: duplicates.
BEAT_ENTRY = "customers.cut_date_watch"

#: Nightly, expressed in SECONDS because every installer in this repo expresses
#: its schedule that way (`work.rules_sweep`, `payments.collections_ladder`,
#: `notifications.dispatch`) and a mixed vocabulary in `app.conf.beat_schedule`
#: is how an entry gets read as the wrong unit. It is a DURATION and not a time
#: — `BR-TEN-043` — and beat owns the clock.
DEFAULT_WATCH_EVERY_SECONDS = 24 * 60 * 60
WATCH_EVERY_SECONDS_ENV = "DISCONNECT_WATCH_EVERY_SECONDS"

#: Comma-separated subdomains, when an operator wants a SUBSET. Unset means
#: every LIVE utility — see the module docstring for why the default is not `()`
#: (DEF-3422, hard-won law 3).
WATCH_TENANTS_ENV = "DISCONNECT_WATCH_TENANTS"

#: The registered task objects, bound by `install()`. ⚠ THE RESULT IS KEPT:
#: `app.task(...)(fn)` returns a NEW object and leaves the module-level name
#: bound to the plain function, which has no `.delay` — so a fan-out written as
#: `watch_one.delay` would run every utility's read INLINE inside beat's own
#: process, silently, with every test passing.
_WATCH_ONE_TASK: Any = None
_WATCH_ALL_TASK: Any = None

#: Carried on every report, exactly as `ladder.LADDER_UNAVAILABLE` is carried on
#: every engine result: a caller must never have to INFER an absence.
WATCH_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "watch_surfaces_on_the_register_only",
        "br_ref": "BR-NOT-021",
        "detail": "what this watch finds reaches a clerk who opens the disconnects register, "
        "and nobody else. The only staff message this product can write is a FAILURE alert — "
        "it refuses a failed count below one and addresses every System Admin — and a cut "
        "falling due is not a failure. Which event a due cut is, and who should be told, is "
        "OQ-CUS-12526 and is open.",
    },
    {
        "code": "watch_never_cuts",
        "br_ref": "BR-CUS-039",
        "detail": "this watch reads cut dates and reports them. It does not cut a supply, "
        "advance a tier, write a notice or move a case out of its state — a person presses "
        "Mark as cut, as they always have. Whether an unattended job may ever perform a cut "
        "is OQ-CUS-12525 and is open.",
    },
)

#: What a firing says when tenancy can answer nothing. A sentence an operator
#: can act on, with no id and no code in it — `collections_schedule`'s posture.
NO_TENANTS_FOUND = (
    "No utility could be read, so no cut dates were looked at. Nothing is missed: the "
    "disconnects register still shows what is due the moment a member of staff opens it, "
    "and the next firing tries again."
)


# ── configuration ─────────────────────────────────────────────────────────
def watch_every_seconds() -> int:
    """The interval, from configuration, with the default as the fallback.

    A value that is not a positive whole number is IGNORED with a log line
    rather than obeyed: a `0` or a `-1` would mean beat firing continuously,
    which is a loop and not a schedule.
    """
    raw = os.environ.get(WATCH_EVERY_SECONDS_ENV, "").strip()
    if not raw:
        return DEFAULT_WATCH_EVERY_SECONDS
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        logger.warning(
            "%s=%r is not a positive number of seconds — the cut-date watch is using "
            "its default of %s instead. A zero or negative interval is not a schedule.",
            WATCH_EVERY_SECONDS_ENV,
            raw,
            DEFAULT_WATCH_EVERY_SECONDS,
        )
        return DEFAULT_WATCH_EVERY_SECONDS
    return seconds


def configured_subdomains() -> tuple[str, ...]:
    """The utilities an OPERATOR named, in the order they wrote them.

    De-duplicated, because the same subdomain twice would be two identical
    reports per firing for one utility.
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
    try:
        target = import_module("apps.tenancy.selectors")
    except ImportError:  # pragma: no cover — tenancy ships in this repo
        return ()
    found = getattr(target, "live_tenant_subdomains", None)
    if not callable(found):  # pragma: no cover — published since DEF-3422
        return ()
    try:
        listed = found()
    except Exception:  # noqa: BLE001 — see the docstring
        logger.exception(
            "the live-utility read could not be made, so no cut dates were looked at. "
            "Nothing is lost — the register answers the same question on demand."
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
    configured = configured_subdomains()
    if configured:
        return configured
    return _live_subdomains()


# ── the beat entry ────────────────────────────────────────────────────────
def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so it can be asserted without
    starting celery — the schedule being CORRECT and the schedule being
    INSTALLED are two different claims, and hard-won law 2 is about exactly that
    gap.
    """
    return {
        BEAT_ENTRY: {
            "task": FANOUT_TASK,
            "schedule": float(
                every_seconds if every_seconds is not None else watch_every_seconds()
            ),
            "args": (),
            "options": {"expires": None},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the schedule and the two tasks on the celery app. Idempotent.

    Called from `CustomersConfig.ready()`. Returns what it did, so a caller and
    a test can tell *installed* from *celery is not importable here* — the two
    look identical from outside and only one of them is a problem. A failure to
    import celery is NOT an error: `manage.py check`, a migration and the test
    suite all run without a broker.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the cut-date watch was not installed: celery is not available here "
                "(%s). Nothing is broken — the register still answers what is due, and "
                "`watch_one` still runs from a terminal.",
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


# ── the watch ─────────────────────────────────────────────────────────────
def watch_all() -> dict[str, Any]:
    """ONE firing: hand every watched utility its own read.

    A fan-out and not a loop, for the reason notifications gives for its own:
    one utility's slow read must not delay another's. Beat discards the return
    value; it exists so a test and an operator running this by hand see the same
    facts.
    """
    subdomains = watched_subdomains()
    if not subdomains:
        logger.warning("the cut-date watch fired: %s", NO_TENANTS_FOUND)
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
                "could not hand %s its cut-date read — its register still answers the "
                "same question on demand and nothing is lost",
                subdomain,
            )
    return {"tenants": list(subdomains), "dispatched": len(subdomains), "problem": None}


def watch_one(subdomain: str, *, as_of: date | None = None) -> dict[str, Any]:
    """ONE utility's cut dates, on ITS business day. Reads; writes nothing.

    Returns the register's own report plus the utility it was read for, so the
    worker log, an operator running this by hand and a test all read the same
    thing.

    `as_of` exists so a test can name a day without freezing a clock
    (`BR-TEN-043`). Left out, it is the utility's own today — `BR-TEN-081`,
    through `seams.tenant_today`, which is the SAME read the register's tiles
    use, so the watch and the screen cannot disagree about what day it is.
    """
    from core import tenancy as core_tenancy

    report: dict[str, Any] = {
        "subdomain": subdomain,
        "read": False,
        "as_of": None,
        "reason": None,
        "problems": [dict(problem) for problem in WATCH_UNAVAILABLE],
    }

    try:
        selectors = import_module("apps.tenancy.selectors")
        lookup = getattr(selectors, "tenant_id_for_subdomain", None)
    except ImportError:  # pragma: no cover — tenancy ships in this repo
        lookup = None
    if not callable(lookup):  # pragma: no cover — published
        report["reason"] = "tenancy_lookup_unavailable"
        logger.error(
            "the cut-date watch cannot resolve %r: apps.tenancy.selectors."
            "tenant_id_for_subdomain is not published, so no utility can be entered.",
            subdomain,
        )
        return report

    tenant_id = lookup(subdomain)
    if tenant_id is None:
        report["reason"] = "unknown_tenant"
        logger.error(
            "the cut-date watch is configured for %r and no utility has that short web "
            "address. Its cut dates were not read; correct %s.",
            subdomain,
            WATCH_TENANTS_ENV,
        )
        return report

    # ⚠ **HARD RULE 1.** Every read below happens with `app.tenant_id` set;
    # RLS is FORCE, so outside this block the queries return nothing at all.
    with core_tenancy.tenant_context(tenant_id):
        return _watch_within_tenant(report, as_of=as_of)


def _watch_within_tenant(report: dict[str, Any], *, as_of: date | None) -> dict[str, Any]:
    """Everything that needs `app.tenant_id` set. Split out so the context above
    reads as one statement and every early return below is inside it."""
    from apps.customers import disconnect_due, seams

    try:
        on = as_of or seams.tenant_today()
    except Exception as problem:  # noqa: BLE001 — one utility, not the firing
        report["reason"] = "business_day_unavailable"
        report["detail"] = str(problem)
        logger.error("the cut-date watch could not name a day for %s: %s", report["subdomain"], problem)
        return report

    try:
        register = disconnect_due.due_register(as_of=on)
    except Exception as problem:  # noqa: BLE001 — one utility, not the firing
        report["reason"] = "register_unreadable"
        report["detail"] = str(problem)
        logger.exception("the cut-date watch could not read %s", report["subdomain"])
        return report

    report.update(register)
    report["read"] = True
    report["reason"] = None
    report["problems"].extend(dict(problem) for problem in register.get("unavailable", ()))
    logger.info(
        "cut-date watch · %s · %s: %s overdue, %s due today, out of %s open cases "
        "(skipped %s with no date, %s already cut, %s awaiting reconnection). "
        "Nothing was cut — the register is where this is worked.%s",
        report["subdomain"],
        register["as_of"],
        register["overdue"],
        register["due_today"],
        register["considered"],
        register["skipped"]["no_cut_date"],
        register["skipped"]["already_cut"],
        register["skipped"]["reconnecting"],
        "".join(
            f"\n    {row['case_no']} · {row['account_no']} · {row['cut_scheduled_for']}"
            + (f" · {row['days_overdue']} days late" if row["days_overdue"] else " · today")
            for row in register["cases"]
        ),
    )
    return report


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-20 (*"Something has to read cut dates daily and
#         surface what's due"*) · apps/payments/collections_schedule.py and
#         apps/work/rules.py (the two existing nightly installers this follows
#         rather than minting a third mechanism) · apps/notifications/schedule.py
#         (`install()` from `ready()`, and DEF-3422's live-tenant default) ·
#         disconnects.NO_SCHEDULER · DEF-320 · B14 rule 31 · NFR-3
# generated: 2026-09-20 by lane DBLD-3 (the cut-date watcher)
# checklist: A✔ B=deferred(no-API-half — a schedule is not a surface; what it
#         reads is already served by `GET /disconnects`) C✔ D=deferred(as above)
#         E=deferred(no-frontend-half in THIS file — the screen half is the
#         register's DUE NOW view, landed in the same commit) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_dbld3_cut_date_watch.py · the beat
#         entry was proved RED before green (hard-won law 7) through the harness
#         that runs it: with `install()` not called from `ready()`,
#         `app.conf.beat_schedule` held no `customers.cut_date_watch` key and
#         the assertion read `KeyError: 'customers.cut_date_watch'`.
# exceptions: (1) **IT CUTS NOTHING AND IT WRITES NOTHING.** No row is created,
#         updated or deleted by any path in this file. OQ-CUS-12525 is open on
#         whether an unattended job may ever perform a cut, and a schedule
#         existing is not permission.
#         (2) **NO BELL MESSAGE** — the only staff entry point refuses a failed
#         count below one and treats every alert as a failure (BR-NOT-021), and
#         a due cut is not a failure. OQ-CUS-12526, open. Carried on every report
#         as `watch_surfaces_on_the_register_only` rather than left silent.
#         (3) **NO SAME-DAY GUARD, DELIBERATELY** — the two neighbouring
#         schedules have one because they WRITE. A repeat firing here costs one
#         log line and produces the identical report.
#         (4) **NO PER-TENANT SWITCH.** `collections_schedule` seeds its own OFF
#         because it writes to customers; a read that surfaces work needs no
#         utility's permission and adding a switch would let a utility turn off
#         the only thing watching its cut dates.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
