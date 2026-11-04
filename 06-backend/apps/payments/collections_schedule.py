# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 CS-10, task 54 — *"Run the collection ladder on a schedule"*.
#           Its ONE new rule, verbatim: *"The scheduled run is per-utility and
#           runs on that utility's business day, not on UTC."*
# Rules:    BR-PAY-017 (the ladder's rungs and its five stop conditions) ·
#           BR-PAY-016 as amended 2026-08-12 (the partial-payment pause) ·
#           BR-CUS-039 / A15 (a medical hold is excluded from EVERY ladder
#           step) · BR-TEN-081 (the utility's OWN clock decides what day it is;
#           `tenant_today()` is the read half) · BR-TEN-043 (the moment is
#           NAMED by the caller, never taken from a wall clock on a money path)
#           · BR-TEN-013 / B1 (a module never touches another module's ORM) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           rule 7 (every money action writes audit_log — `run_ladder` does) ·
#           hard-won law 2 (built is not wired) · law 3 (defaults fail closed)
# Defects:  DEF-3150 (per PASS is not per DAY — the same-day guard this
#           schedule depends on, fixed in `ladder.decide`) ·
#           DEF-2805 (a job killed by the HARD task limit is left `running`
#           for ever — the reason this is a plain celery task and NOT a BE-07
#           `jobs` record; see "WHY THERE IS NO JOB RECORD" below)
# Tests:    06-backend/tests/test_cr059_cs10_collections_schedule.py
# Impacts:  apps/payments/apps.py (`ready()` installs the schedule) ·
#           apps/payments/ladder.py (the engine this fires, unchanged except
#           for DEF-3150's guard) · apps/tenancy/settings_families.COLLECTIONS
#           (the two S70 parameters this reads) · docker-compose.yml's
#           `celery-beat` service (which fires it)
# ───────────────────────────────────────────────────────
"""The collection ladder, on each utility's OWN business day.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE GAP THIS CLOSES, IN THE CODE'S OWN WORDS.                          ║
╚══════════════════════════════════════════════════════════════════════════╝
`ladder.LADDER_UNAVAILABLE` has carried this sentence on **every result the
engine has ever returned**:

    "BR-PAY-017's ladder is evaluated on a schedule and this repo's job runner
     registers no collections job … nothing runs it nightly. Until it does, the
     ladder advances only when a human asks it to."

For a utility with one or two staff, a chase that depends on somebody
remembering is a chase that stops.

────────────────────────────────────────────────────────────────────────────
⚠ THE BUSINESS DAY IS THE WHOLE POINT, AND A CRON ENTRY CANNOT EXPRESS IT
────────────────────────────────────────────────────────────────────────────
A celery-beat entry has ONE schedule for the whole deployment. Eleven utilities
in eleven timezones do not share a 6 a.m., and the day a ladder step falls on is
the day a customer is chased. **Running on UTC would send a 48-hour certified
notice a day early for a utility west of UTC** — CS-10 says exactly that — and
on a weekend or a holiday it chases somebody on a day the utility is shut.

So the shape here is a **SWEEP, not an alarm.** Beat fires this every
`COLLECTIONS_LADDER_EVERY_SECONDS` (default 900 — fifteen minutes), and each
firing asks each configured utility one question: *is it your hour yet, on your
clock?* The utility whose hour it is runs; the others do not. Beat owns a
DURATION; this file owns the per-tenant DECISION. That is the same division
`apps/notifications/schedule.py` made for the dispatcher, and for the same
BR-TEN-043 reason.

**The DAY comes from `apps.tenancy.selectors.tenant_today()`** — the published
read half of BR-TEN-081, the seam `apps/payments/settings_seam.tenant_timezone`
already points at, and the one other modules use. Nothing here re-derives it: a
second copy of "what day is it for this tenant" is DEF-094 rebuilt, where the
read half was fixed and the write half went on answering UTC.

**The HOUR is read once and checked against the day.** A scheduler cannot avoid
asking what time it is — that is what a scheduler IS — but it can avoid asking
twice. `_tenant_moment()` takes ONE instant in the tenant's zone, and if the day
it implies disagrees with `tenant_today()` we are inside the midnight boundary:
this sweep REPORTS and runs nothing, and the next one fifteen minutes later is
unambiguous. A ladder step taken under two different opinions of what day it is
is precisely the bug BR-TEN-043 exists to prevent.

────────────────────────────────────────────────────────────────────────────
⚠ WHAT IT REFUSES TO RUN WITHOUT, AND WHY EACH REFUSAL IS THE SAFE DIRECTION
────────────────────────────────────────────────────────────────────────────
An unattended job is not a clerk. A clerk pressing *Run ladder* on S34 is
looking at the account; a job at 6 a.m. is looking at nobody, and every step it
takes ends in a letter with a disconnection date on it. So the unsafe option is
the one that has to be TYPED (hard-won law 3), and there are three:

  1. **THE SWITCH IS OFF UNTIL A UTILITY TURNS IT ON.**
     `collections_schedule_enabled` seeds **False**. Deploying this code chases
     nobody. A schedule that started writing to customers the moment it shipped
     would be a change to a utility's collections practice made by a deploy.

  2. **NO MEDICAL-HOLD READ, NO RUN.** BR-CUS-039 excludes a medical-hold
     account from EVERY ladder step, and `ladder.run_ladder` takes the holds as
     an ARGUMENT — it may not infer a clinical fact (its own exception 5).
     `apps.customers.disconnects.medical_hold_for` exists and, until this file,
     **had no caller anywhere**; that module says so in its own docstring
     (*"AND NOTHING CALLS IT YET … the call site is a `_resolve` in payments
     and notifications, in files this lane does not own"*). It is resolved here
     by name. When it cannot be resolved the sweep REFUSES the tenant rather
     than running with no exclusions: chasing a household on a medical
     certificate to a certified disconnection notice is not an error you undo
     with a correcting row.

  3. **NO TENANT SETTINGS, NO RUN.** `settings_seam` already refuses rather
     than falling back to BR-PAY-017's defaults, in its own words: *"an
     unreachable setting is not a setting, and every step it takes reaches a
     real customer with a real disconnection date."* That refusal is caught
     here and REPORTED per tenant, so one misconfigured utility cannot stop the
     others' sweeps.

────────────────────────────────────────────────────────────────────────────
⚠ WHAT IT CANNOT DO, STATED RATHER THAN LEFT TO BE DISCOVERED (law 1)
────────────────────────────────────────────────────────────────────────────
**THE PARTIAL-PAYMENT PAUSE DOES NOT FIRE, AND IT NEVER HAS.** BR-PAY-016 as
amended 2026-08-12 pauses the ladder when a partial payment clears the tenant's
percentage — one of the five stop conditions §7 lists — and `run_ladder` takes
that figure through `recent_payments`, which **no caller in this repository has
ever supplied**, this one included. `POST /collections/run` does not supply it
either, so the gap is older than the schedule and is not created here. It is
`DEF-3151`, and what it needs before it can be closed is a ruling this file may
not make: *"recently" over WHAT WINDOW* — `OQ-1320`. Carried on every result
rather than left silent, because a stop condition that never stops anything is
the exact shape of hard-won law 2.

**WHY THERE IS NO JOB RECORD (`DEF-2805`).** BE-07's `jobs` rows are the right
home for work a person is waiting on and can poll. This is not that: nobody is
watching at 6 a.m., there is no poll URL to hand anybody, and a job killed by
the HARD task time limit is left `running` for ever and cannot be resumed —
which for a nightly sweep would mean a stranded row appearing every single day.
A plain celery task fails, logs, and the next sweep is a clean attempt. This is
the same choice `apps/notifications/schedule.py` made, for the same reason.

**WHAT S34 STILL CANNOT SHOW.** CS-10 asks Outstandings for *"when it last ran,
what it did and when it runs next"*. `status()` below answers *when it runs
next* and *whether it is on*, from configuration — it cannot answer *when it
last ran* or *what it did*, because nothing in this product records a ladder
PASS. That record is a table (`(tenant, business_date)` unique — B2's own
idempotency idiom) and it is deliberately not created here: it belongs with the
P12/S34 screen that reads it (CR-059 task 55), and a table with no reader is
the built-not-wired shape law 2 forbids. `OQ-1321`.

────────────────────────────────────────────────────────────────────────────
⚠ WOULD IT ACTUALLY FIRE? TWO ANSWERS, AND ONLY ONE OF THEM IS YES
────────────────────────────────────────────────────────────────────────────
**In `docker-compose.yml`: YES.** `celery-beat` runs `celery -A config.celery
beat` with `deploy.replicas: 1`, which imports Django, which runs every
`AppConfig.ready()`, which is where `install()` below is called — the identical
path `apps/notifications/schedule.py` proved end to end on 2026-08-29 (CR-048
B5).

**On the host this product is deployed to: NO, and not because of anything
here.** `09-infra/01-deployment-architecture.md` §4.1 records that that host
carries a pre-existing `.env` and needs three things done ON IT — a reachable
broker at its own `CELERY_BROKER_URL`, at least one worker process, and
`JOBS_EAGER=false` — and that *"until all three are true there … the code is
correct and nothing is running it"* (hard-won law 4: a template change never
reaches a host that already has a `.env`). Registering this entry does not
change that and does not claim to. **On that host this schedule is a
registration nothing runs**, and the sentence on S34 saying nothing chases
overnight stays true there until an operator makes it false.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from importlib import import_module
from typing import Any

logger = logging.getLogger("smartbillhub.payments.collections_schedule")

#: The two routing names, pinned as LITERALS for `apps/tenancy/tasks.py`'s own
#: reason: *"a renamed task is a message nobody consumes, and the queue says
#: nothing about it."* A module move must not orphan messages already in flight.
LADDER_TASK = "smartbillhub.payments.collections_ladder"
FANOUT_TASK = "smartbillhub.payments.collections_ladder_all"

#: The registered task objects, bound by `install()`. See the ⚠ note inside it
#: for why `app.task(...)`'s return value has to be KEPT rather than discarded.
_LADDER_ONE_TASK: Any = None
_LADDER_ALL_TASK: Any = None

#: The beat entry's own name. ONE key, so installing twice replaces rather than
#: duplicates — two entries would be two sweeps per interval, and beat running
#: twice is the single-beat hazard `docker-compose.yml` warns about arriving by
#: another door.
BEAT_ENTRY = "payments.collections_ladder"

#: How often beat fires the sweep. SECONDS, because it is a DURATION and not a
#: time (BR-TEN-043) — see the module docstring for why an alarm cannot work.
#:
#: ⚠ **THE DEFAULT IS ALSO THE WIDTH OF THE FIRING WINDOW.** `run_one` runs a
#: tenant only in the FIRST sweep of its configured hour (`minute < the sweep in
#: minutes`), so that one hour produces one pass rather than four. Set this to a
#: value that divides an hour; anything else still works — the engine's own
#: same-day guard (`DEF-3150`) is what makes a repeat harmless — but it costs a
#: skip row per debtor per extra sweep.
DEFAULT_SWEEP_EVERY_SECONDS = 900
SWEEP_EVERY_SECONDS_ENV = "COLLECTIONS_LADDER_EVERY_SECONDS"

#: Comma-separated tenant subdomains this deployment sweeps.
#:
#: ⚠ **THIS IS CONFIGURATION AND NOT A QUERY, AND IT HAS TO BE.** B1 /
#: BR-TEN-013 forbid reading `tenancy.Tenant` from this module and tenancy
#: publishes no "every live tenant" selector — `apps/notifications/schedule.py`
#: records the same absence and `dispatch_outbound` has no `--all-tenants` for
#: the same reason. Leave it unset and every sweep REPORTS that no utility is
#: configured rather than looking healthy. The day tenancy publishes a
#: live-tenant read, `scheduled_subdomains()` is the one function that changes.
LADDER_TENANTS_ENV = "COLLECTIONS_LADDER_TENANTS"

#: The two S70 parameters, named once so the contract is greppable from both
#: sides of the boundary (`apps/tenancy/settings_families.COLLECTIONS`).
KEY_SCHEDULE_ENABLED = "collections_schedule_enabled"
KEY_SCHEDULE_HOUR = "collections_schedule_hour"

#: What a sweep reports when nobody has configured a tenant. A sentence an
#: operator can act on, with no id and no code in it — B14 rule 32's posture,
#: and CR-048's own rule about refusals — because it is read by whoever is
#: wondering why nobody is being chased.
NO_TENANTS_CONFIGURED = (
    "No utility is set up for the scheduled collection sequence, so nothing was "
    "chased. Nobody is missed: the sequence still runs when a member of staff "
    "asks for it on the Outstandings screen. Add each utility's short web "
    "address to the scheduled-collections setting on the server and their "
    "reminders and notices will go out on their own."
)

#: Carried on every scheduled result, exactly as `ladder.LADDER_UNAVAILABLE` is
#: carried on every engine result: a caller must never have to INFER an absence.
SCHEDULE_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "partial_payment_pause_not_supplied",
        "br_ref": "BR-PAY-016",
        "detail": "BR-PAY-016 as amended 2026-08-12 pauses the ladder when a partial payment "
        "clears this utility's percentage, and `ladder.run_ladder` takes that figure through "
        "`recent_payments` — which NO caller in this repository supplies, this schedule and "
        "`POST /collections/run` included (DEF-3151). So one of BR-PAY-017's five stop "
        "conditions never stops anything, on the scheduled run and on the manual one alike. "
        "Closing it needs a ruling this module may not make: what window 'recently' means "
        "(OQ-1320).",
    },
    {
        "code": "no_pass_record",
        "br_ref": "BR-PAY-017",
        "detail": "nothing in this product records a ladder PASS, so this schedule can say "
        "when it will next run and whether it is switched on, and cannot say when it last ran "
        "or what it did. S34's panel needs all four (CR-059 CS-10). The record is a table keyed "
        "on the utility and its business day, and it belongs with the screen that reads it "
        "(OQ-1321).",
    },
)


# ── configuration ─────────────────────────────────────────────────────────
def sweep_every_seconds() -> int:
    """The sweep interval, from configuration, with the default as the fallback.

    A value that is not a positive whole number is IGNORED with a log line
    rather than obeyed: a `0` or a `-1` would mean beat firing continuously,
    which would walk every debtor of every configured utility in a loop.
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
            "%s=%r is not a positive number of seconds — the collections sweep is "
            "using its default of %s instead. A zero or negative interval is not a "
            "schedule, it is a loop.",
            SWEEP_EVERY_SECONDS_ENV,
            raw,
            DEFAULT_SWEEP_EVERY_SECONDS,
        )
        return DEFAULT_SWEEP_EVERY_SECONDS
    return seconds


def scheduled_subdomains() -> tuple[str, ...]:
    """The utilities this deployment sweeps, in the order the operator wrote them.

    De-duplicated: the same subdomain twice would be two passes per sweep for one
    utility. The engine's same-day guard would make the second one harmless, and
    it would still write a skip row for every debtor — so it is removed here
    rather than absorbed downstream.
    """
    raw = os.environ.get(LADDER_TENANTS_ENV, "")
    seen: list[str] = []
    for part in raw.split(","):
        subdomain = part.strip().lower()
        if subdomain and subdomain not in seen:
            seen.append(subdomain)
    return tuple(seen)


# ── the beat entry ────────────────────────────────────────────────────────
def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so it can be asserted in a
    test without starting celery — the schedule being CORRECT and the schedule
    being INSTALLED are two different claims, and hard-won law 2 is about
    exactly that gap.
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

    Called from `PaymentsConfig.ready()`. Returns what it did, so a caller (and
    a test) can tell *installed* from *celery is not importable here* — the two
    look identical from outside and only one of them is a problem.

    A failure to import celery is NOT an error: `manage.py check`, a migration
    and the whole test suite run without a broker, and a Django app that refused
    to start because a scheduler is absent would be a worse product than one
    whose reminders go out when the worker comes back.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the collections ladder schedule was not installed: celery is not "
                "available here (%s). Nothing is broken — the ladder still runs from "
                "the Outstandings screen, which is the only thing that ran it before.",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    # ⚠ THE RESULT IS KEPT, and that is not tidiness. `app.task(...)(fn)` returns
    # a NEW task object and leaves the module-level name bound to the plain
    # function, which has no `.delay`. A fan-out written as `run_one.delay` would
    # therefore fall through to walking every tenant's debtors INLINE inside
    # beat's own process — one utility's slow ladder delaying every other
    # utility's, silently, with every test passing.
    global _LADDER_ONE_TASK, _LADDER_ALL_TASK
    _LADDER_ONE_TASK = app.task(name=LADDER_TASK, bind=False)(run_one)
    _LADDER_ALL_TASK = app.task(name=FANOUT_TASK, bind=False)(run_all)

    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


# ── the seams (resolved by NAME at call time, never imported — B1) ─────────
def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom every seam in this module uses, so no
    import statement binds payments to tenancy's or customers' internals and
    nothing here needs re-wiring when an owner moves a function.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _tenant_moment(zone: Any) -> datetime:
    """ONE instant, in the utility's own zone. The only clock read in this file.

    `django.utils.timezone.now()` is the same call `tenant_today()` makes, so
    the hour tested here and the day the ladder is run for come from one clock —
    see `run_one` for the boundary check that proves they agree.
    """
    from django.utils import timezone as dj_timezone

    return dj_timezone.now().astimezone(zone)


# ── the sweep ─────────────────────────────────────────────────────────────
def run_all() -> dict[str, Any]:
    """ONE sweep: hand every configured utility its own turn.

    A fan-out and not a loop: each utility's turn is its own task, so one
    utility's slow ladder — or its broken settings — cannot delay another's
    chase. Beat discards the return value; it exists so a test and an operator
    running this by hand see the same facts.
    """
    subdomains = scheduled_subdomains()
    if not subdomains:
        logger.warning("collections ladder sweep fired: %s", NO_TENANTS_CONFIGURED)
        return {"tenants": [], "dispatched": 0, "problem": NO_TENANTS_CONFIGURED}

    for subdomain in subdomains:
        try:
            if _LADDER_ONE_TASK is not None:
                _LADDER_ONE_TASK.delay(subdomain)
            else:
                # `install()` has not run (celery absent, or this was called by
                # hand). Run it inline rather than silently doing nothing — a
                # fan-out that dispatches nowhere and reports success is the
                # shape DEF-320 was.
                run_one(subdomain)
        except Exception:  # noqa: BLE001 — one tenant's broker error is not all of them
            logger.exception(
                "could not hand %s its collections turn — its debtors wait for the "
                "next sweep and nothing is lost",
                subdomain,
            )
    return {"tenants": list(subdomains), "dispatched": len(subdomains), "problem": None}


def run_one(subdomain: str, *, force: bool = False) -> dict[str, Any]:
    """ONE utility's turn: run the ladder if it is that utility's hour, on its day.

    Returns a plain dict of FACTS — what day it decided for, what it did, and
    every reason it did not — so the worker log, an operator running this by
    hand and a test all read the same thing.

    `force` skips the hour test and NOTHING else: the switch, the settings and
    the medical-hold read still gate it. It exists so an operator can run a
    utility's ladder for its own business day after a broker outage, without
    waiting for tomorrow's hour, and so a test can prove the rest of the path
    without freezing a clock.
    """
    from core import tenancy as core_tenancy

    report: dict[str, Any] = {
        "subdomain": subdomain,
        "ran": False,
        "as_of": None,
        "reason": None,
        "stepped": [],
        "skipped": [],
        "problems": [dict(problem) for problem in SCHEDULE_UNAVAILABLE],
    }

    lookup = _resolve("tenancy", "tenant_id_for_subdomain")
    if lookup is None:  # pragma: no cover - tenancy publishes it
        report["reason"] = "tenancy_lookup_unavailable"
        logger.error(
            "the collections sweep cannot resolve %r: apps.tenancy.selectors."
            "tenant_id_for_subdomain is not published, so no utility can be entered.",
            subdomain,
        )
        return report
    tenant_id = lookup(subdomain)
    if tenant_id is None:
        report["reason"] = "unknown_tenant"
        logger.error(
            "the collections sweep is configured for %r and no utility has that short "
            "web address. Nobody was chased for it; correct %s.",
            subdomain,
            LADDER_TENANTS_ENV,
        )
        return report

    with core_tenancy.tenant_context(tenant_id):
        return _run_within_tenant(report, force=force)


def _run_within_tenant(report: dict[str, Any], *, force: bool) -> dict[str, Any]:
    """Everything that needs `app.tenant_id` set. Split out so the context above
    reads as one statement and every early return below is inside it."""
    from apps.payments import billing_seam, ladder, settings_seam
    from apps.payments.exceptions import PaymentRuleError

    # ── 1 · the utility's own clock (BR-TEN-081) ──────────────────────────
    today = _tenant_today(report)
    if today is None:
        return report
    try:
        moment = _tenant_moment(settings_seam.tenant_timezone())
    except PaymentRuleError as refusal:
        report["reason"] = "tenant_timezone_unavailable"
        report["detail"] = str(refusal)
        return report

    if moment.date() != today:
        # Inside the midnight boundary: the instant this file read and the day
        # tenancy answered disagree. A ladder step taken under two opinions of
        # what day it is is the bug BR-TEN-043 exists to prevent, so nothing
        # runs and the next sweep is unambiguous.
        report["reason"] = "midnight_boundary"
        report["as_of"] = today.isoformat()
        return report
    report["as_of"] = today.isoformat()

    # ── 2 · is this utility switched on, and is it its hour? ───────────────
    try:
        enabled = schedule_enabled()
        hour = schedule_hour()
    except PaymentRuleError as refusal:
        # `settings_seam` refuses rather than falling back to BR-PAY-017's
        # defaults, and its reason is the right one to surface: an unreachable
        # setting is not a setting. One misconfigured utility, not the sweep.
        report["reason"] = "settings_unavailable"
        report["detail"] = str(refusal)
        logger.error("collections schedule for %s: %s", report["subdomain"], refusal)
        return report

    if not enabled:
        report["reason"] = "schedule_off"
        return report
    if not force:
        if moment.hour != hour:
            report["reason"] = "not_the_hour"
            report["next_run_at"] = _next_run_at(moment, hour).isoformat()
            return report
        # Only the FIRST sweep of the hour runs, so one hour is one pass rather
        # than one per sweep. The engine's same-day guard (DEF-3150) makes a
        # repeat harmless either way; this keeps it from writing a skip row per
        # debtor per extra sweep.
        if moment.minute >= _sweep_minutes():
            report["reason"] = "already_swept_this_hour"
            return report

    # ── 3 · BR-CUS-039 — no medical-hold read, no run (law 3) ─────────────
    positions, seam_problems = billing_seam.outstanding_positions()
    report["problems"].extend(dict(problem) for problem in seam_problems)
    account_ids = tuple(position.account_id for position in positions)
    if not account_ids:
        report["reason"] = "nobody_owes_anything"
        return report

    holds, hold_problem = _medical_holds(account_ids, as_of=today)
    if hold_problem is not None:
        report["reason"] = "medical_hold_unreadable"
        report["problems"].append(hold_problem)
        logger.error(
            "the collections ladder did NOT run for %s on %s: %s",
            report["subdomain"],
            today,
            hold_problem["detail"],
        )
        return report

    # ── 4 · run it, on the tenant's business day ──────────────────────────
    try:
        run = ladder.run_ladder(
            account_ids=account_ids,
            as_of=today,
            # `actor=None` is what makes `run_ladder`'s audit row stamp
            # `job: "payments.ladder.run"` instead of a person (hard rule 7).
            actor=None,
            partial_pause_percent=settings_seam.partial_pause_percent(),
            medical_hold_account_ids=holds,
        )
    except PaymentRuleError as refusal:
        report["reason"] = "ladder_refused"
        report["detail"] = str(refusal)
        logger.error("the collections ladder refused for %s: %s", report["subdomain"], refusal)
        return report

    report["ran"] = True
    report["reason"] = None
    report["accounts"] = len(account_ids)
    report["stepped"] = [
        {"account_id": decision.account_id, "rung": decision.rung} for decision in run.stepped
    ]
    report["skipped"] = [
        {"account_id": decision.account_id, "reason": decision.skip_reason}
        for decision in run.skipped
    ]
    report["problems"].extend(dict(problem) for problem in run.problems)
    logger.info(
        "collections ladder for %s on %s: %s account(s), %s stepped, %s skipped",
        report["subdomain"],
        today,
        len(account_ids),
        len(report["stepped"]),
        len(report["skipped"]),
    )
    return report


def _tenant_today(report: dict[str, Any]) -> date | None:
    """BR-TEN-081's read half, through the seam and never re-derived here."""
    read = _resolve("tenancy", "tenant_today")
    if read is None:  # pragma: no cover - tenancy publishes it
        report["reason"] = "tenant_today_unavailable"
        return None
    answer = read()
    return answer if isinstance(answer, date) else None


def _medical_holds(
    account_ids: tuple[Any, ...], *, as_of: date
) -> tuple[tuple[Any, ...], dict[str, Any] | None]:
    """A15 / BR-CUS-039's exclusions — or the named reason there are none.

    ⚠ **THE SECOND RETURN IS NOT AN EMPTY TUPLE AND THE DIFFERENCE IS A
    HOUSEHOLD ON A MEDICAL CERTIFICATE.** An empty tuple means *nobody on this
    list is protected*; a problem means *nobody could ask*, and a caller that
    read the second as the first would post a certified disconnection notice to
    a customer the rule excludes from every step. `run_one` refuses on it.
    """
    read = _resolve("customers", "medical_hold_for", "disconnects")
    if read is None:
        return (), {
            "code": "medical_hold_not_readable",
            "br_ref": "BR-CUS-039",
            "detail": "apps.customers.disconnects.medical_hold_for is not published, so the "
            "A15 exclusion cannot be applied. The scheduled run is REFUSED rather than run "
            "without it: `ladder.run_ladder` takes the holds as an argument and never infers "
            "a clinical fact, and an unattended job that chased a household on a medical "
            "certificate would do it with nobody watching.",
        }
    held: list[Any] = []
    for account_id in account_ids:
        try:
            if read(account_id, as_of=as_of):
                held.append(account_id)
        except Exception as problem:  # noqa: BLE001 — the whole run refuses, see below
            return (), {
                "code": "medical_hold_not_readable",
                "br_ref": "BR-CUS-039",
                "detail": "the A15 medical-hold exclusion could not be read for every account "
                f"on this list ({problem}), so the scheduled run is REFUSED. A partial answer "
                "is the dangerous one: the accounts that WERE readable would be chased and the "
                "one that was not is the one nobody looked at.",
            }
    return tuple(held), None


# ── the settings this schedule reads (S70) ────────────────────────────────
def schedule_enabled() -> bool:
    """Is the scheduled collection sequence switched on for this utility?

    Seeded **False** — see the module docstring, refusal 1. Anything that is not
    a real boolean is read as OFF for the same reason: the direction that has to
    be typed is the one that writes to customers.
    """
    from apps.payments import settings_seam

    raw = settings_seam.collections().get(KEY_SCHEDULE_ENABLED, False)
    return raw is True or str(raw).strip().lower() in {"true", "1", "yes", "on"}


def schedule_hour() -> int:
    """The hour of the utility's OWN day the sequence runs at, 0–23.

    Refused rather than defaulted when it is not a whole number in range: an
    hour nobody can read is not an hour, and the alternative — picking one — is
    this module deciding when a utility writes to its customers.
    """
    from apps.payments import settings_seam
    from apps.payments.exceptions import PaymentRuleError

    raw = settings_seam.collections().get(KEY_SCHEDULE_HOUR)
    try:
        hour = int(raw)
    except (TypeError, ValueError) as exc:
        raise PaymentRuleError(
            f"this utility's {KEY_SCHEDULE_HOUR} is {raw!r}, which is not an hour of the day. "
            "The scheduled collection sequence is refused rather than run at an hour nobody "
            "chose.",
            br_ref="BR-PAY-017",
        ) from exc
    if not 0 <= hour <= 23:
        raise PaymentRuleError(
            f"this utility's {KEY_SCHEDULE_HOUR} is {hour}, and an hour of the day is 0 to 23. "
            "The scheduled collection sequence is refused rather than run at a time that does "
            "not exist.",
            br_ref="BR-PAY-017",
        )
    return hour


def _sweep_minutes() -> int:
    """The sweep interval in whole minutes, at least 1 — the firing window."""
    return max(1, sweep_every_seconds() // 60)


def _next_run_at(moment: datetime, hour: int) -> datetime:
    """The next instant, in the utility's OWN zone, this schedule would fire.

    A DERIVATION from the hour the utility chose, not a stored fact — so it
    cannot go stale against the setting, and a utility that moves its hour sees
    the new answer immediately.
    """
    from datetime import timedelta

    candidate = moment.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= moment:
        candidate = candidate + timedelta(days=1)
    return candidate


def status() -> dict[str, Any]:
    """What S34 and S70 can truthfully say about this utility's schedule.

    ⚠ **THREE OF CS-10's FOUR FACTS, AND THE FOURTH IS NAMED RATHER THAN
    GUESSED.** *Switched on*, *the hour*, and *when it next runs* are all
    derivable from configuration. *When it last ran and what it did* is not:
    nothing records a ladder pass (`OQ-1321`, and `SCHEDULE_UNAVAILABLE`
    carries it on every result). `last_run_at` is therefore absent from this
    payload rather than served as `null`, which a screen would render as
    *"never"* — and *"never"* is a claim, not an absence.

    Called inside tenant context. Never reads a clock for a DATE: the next-run
    instant is derived from the hour the utility chose, in the utility's zone.
    """
    from apps.payments import settings_seam
    from apps.payments.exceptions import PaymentRuleError

    payload: dict[str, Any] = {
        "registered": True,
        "sweep_every_seconds": sweep_every_seconds(),
        "problems": [dict(problem) for problem in SCHEDULE_UNAVAILABLE],
    }
    try:
        payload["enabled"] = schedule_enabled()
        payload["hour"] = schedule_hour()
        moment = _tenant_moment(settings_seam.tenant_timezone())
    except PaymentRuleError as refusal:
        payload["enabled"] = False
        payload["problems"].append(
            {
                "code": "collections_schedule_unreadable",
                "br_ref": "BR-PAY-017",
                "detail": str(refusal),
            }
        )
        return payload
    payload["next_run_at"] = (
        _next_run_at(moment, payload["hour"]).isoformat() if payload["enabled"] else None
    )
    return payload


def is_live() -> bool:
    """Does a scheduled caller actually advance THIS utility's ladder?

    Read by `ladder.ladder_problems()` to decide whether the `no_scheduled_caller`
    sentence is still TRUE for this tenant. Both halves have to hold and neither
    implies the other: the tasks have to be REGISTERED on a celery app, and the
    utility has to have SWITCHED THE SCHEDULE ON.

    ⚠ **WHAT THE FIRST HALF DOES NOT PROVE, said plainly because a check that
    cannot fail is worse than no check (hard-won law 1).** `_LADDER_ALL_TASK is
    not None` proves `install()` ran and celery was importable. It does NOT
    prove a **beat** process is alive: a deployment running only a worker
    registers the task too. Nothing in this process can observe beat — the
    honest signal is a record of a PASS, which is exactly what `OQ-1321` asks
    for and what does not exist. So the sentence is currently withdrawn on the
    strength of the two facts that CAN be established, and the second of them is
    a deliberate human act on a screen.

    **Answers False on anything it cannot establish**, deliberately: a screen
    that stops saying *"nothing chases overnight"* on a deployment where nothing
    does is hard-won law 1 with the sign flipped — a comment claiming a
    guarantee, printed for a clerk.
    """
    if _LADDER_ALL_TASK is None:
        return False
    try:
        return schedule_enabled()
    except Exception:  # noqa: BLE001 — an unreadable setting is not a live schedule
        return False


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 CS-10 task 54 (12-governance/11-change-requests.md → CR-059 §8 CS-10, §7 "Collections" and §11 row 54 · apps/payments/ladder.py exception (2) · apps/notifications/schedule.py, the one existing beat entry and the shape this follows · 09-infra/01-deployment-architecture.md §4.1 and §10 item 3)
# generated: 2026-09-02 by story-coder (CR-059 W10 collections-schedule lane)
# checklist: A✔ B=deferred(no-API-half — a schedule is not a surface; `status()` is published for CR-059 task 55's S34/S70 panels and is mounted by that lane) C✔ D=deferred(no-API-half, as above) E=deferred(no-frontend-half — task 55 owns P12/S34/S70) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr059_cs10_collections_schedule.py · the schedule was proved RED before green (hard-won law 7) — with `install()` not called from `ready()`, `app.conf.beat_schedule` held no `payments.collections_ladder` key; the same-day guard was proved RED against the unfixed `ladder.decide`, where a second pass on one `as_of` stepped a second rung
# exceptions: (1) NO CLOCK DECIDES A DATE HERE. beat owns a DURATION and `tenant_today()` owns the DAY; the one instant this file reads decides only WHETHER to fire, and disagreement between the two is refused as `midnight_boundary` rather than resolved
#         (2) THE TENANT LIST IS OPERATOR CONFIGURATION, not a query — B1/BR-TEN-013 forbid reading `tenancy.Tenant` here and tenancy publishes no live-tenant read (`apps/notifications/schedule.py` records the same absence). Unset, every sweep REPORTS it
#         (3) THE PARTIAL-PAYMENT PAUSE DOES NOT FIRE and never has — `recent_payments` has no supplier anywhere in this repository (DEF-3151); the window it needs ruling is OQ-1320. Carried in `SCHEDULE_UNAVAILABLE` on every result rather than left silent
#         (4) NO PASS RECORD, so S34 cannot say when the ladder last ran or what it did (OQ-1321). The table belongs with task 55's screen; building it here would be a table with no reader
#         (5) NO BE-07 JOB RECORD, deliberately — DEF-2805 leaves a hard-limit-killed job `running` for ever, which for a daily sweep is a stranded row every day. A plain celery task fails and the next sweep is a clean attempt
#         (6) IT DOES NOT FIRE ON THE DEPLOYED HOST and this file does not claim it does — 09-infra §4.1's two JOBS_EAGER rows name the three things that host needs done ON IT (hard-won law 4)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
