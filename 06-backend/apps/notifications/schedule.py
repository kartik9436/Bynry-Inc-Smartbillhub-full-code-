# ── Trace ──────────────────────────────────────────────
# Change:   CR-048 wave B, task B5 — *"Give the dispatcher a schedule — the
#           scheduler runs today with nothing to fire"*
#           (12-governance/11-change-requests.md → CR-048 step 5)
# Rules:    BR-NOT-005 (the dispatcher sends in tenant-config batches at the
#           PROVIDER's pace — a schedule is how pacing happens, and a drain
#           loop is what it forbids) · BR-NOT-013 (delivery is out of this
#           release on print, email and SMS — they rest queued with a reason) ·
#           BR-NOT-019 (in_app is a real channel and the one that delivers) ·
#           BR-NOT-009 (quiet hours — the cycle re-checks the window each time,
#           which is only meaningful if something fires more than once) ·
#           BR-TEN-013 (a module never touches another module's ORM) ·
#           BR-TEN-043 (event time is named by the caller, never read from a
#           clock — NOTHING HERE READS ONE, see below) · CLAUDE.md rule 1
#           (tenant scoping) · rule 6 (a replayed cycle sends nothing twice)
# Tests:    06-backend/tests/test_cr048_b_engine_on.py
# Impacts:  apps/notifications/apps.py (`ready()` installs the schedule) ·
#           apps/notifications/management/commands/dispatch_outbound.py (the
#           runner this fires, unchanged) · docker-compose.yml's `beat` service,
#           whose own comment says it "has nothing to fire yet" — this is the
#           first thing it fires
# ───────────────────────────────────────────────────────
"""The dispatch schedule — celery beat's first entry in this repo.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE GAP THIS CLOSES, IN THE REPO'S OWN WORDS.                          ║
╚══════════════════════════════════════════════════════════════════════════╝
Three files said the same thing in three places and none of them was wrong:

* `docker-compose.yml`, on the beat service — *"IT HAS NOTHING TO FIRE YET …
  This container connects to the broker and sits there."*
* `dispatch_outbound.py` — *"NOTHING SCHEDULES THIS. There is no celery-beat
  wiring and no cron entry in this repo … an operator runs it."*
* `dispatcher.py` — *"There is no scheduler in this repo, so nothing calls this
  function on a timer yet — REPORTED (hard-won law 2: built is not wired)."*

So the queue filled and never drained, and the ONE channel with a working
adapter delivered only when a person typed a command. That is the difference
between a product and a demonstration.

────────────────────────────────────────────────────────────────────────────
NOTHING HERE READS A CLOCK, AND THE REASON IS NOT A GATE
────────────────────────────────────────────────────────────────────────────
BR-TEN-043 says the moment is NAMED by the caller. A schedule is the one thing
that looks like it must own a clock, and it does not: **beat owns the clock, and
this file owns the schedule** — an interval in seconds, which is a duration and
not a time. When the interval elapses, the task hands over to
`manage.py dispatch_outbound`, and that command already names the instant once
(`now = datetime.now(dt_timezone.utc)`) and passes it down through the whole
cycle. That boundary already existed and is deliberately reused rather than
duplicated: a second clock read here would mean the window check and the
schedule decision could be made against two different instants a few
milliseconds apart, which is exactly the bug the rule exists to prevent.

**Which is also why the task calls the COMMAND and not `dispatch_cycle`
directly.** Calling the service would have obliged this file to resolve the
tenant, name the moment and enter tenant context — three things the runner
already does, correctly, with its refusals already written. Two runners is two
places to fix the next time any of the three changes.

────────────────────────────────────────────────────────────────────────────
ONE CYCLE PER FIRING. NEVER A DRAIN.
────────────────────────────────────────────────────────────────────────────
BR-NOT-005 paces at the provider's rate. A firing takes ONE batch per channel
(at most the tenant's `dispatch_batch_size`, default 500) and stops. Draining
10,000 rows is twenty firings spaced by the interval — which is what the rule
means by *"at the provider's pace"*, and a `--cycles 20` schedule would be the
platform-speed blast T5-24 step 2 measures against.

The default interval is five minutes. It is a PARAMETER
(`NOTIFICATIONS_DISPATCH_EVERY_SECONDS`), not a decision this file makes for
every utility: a small water utility issuing 900 bills a month wants nothing
from a faster clock, and a utility whose ESP throttles wants a slower one.

────────────────────────────────────────────────────────────────────────────
⚠ WHICH TENANTS IT FIRES FOR, AND WHY THAT IS CONFIGURATION AND NOT A QUERY
────────────────────────────────────────────────────────────────────────────
**This module cannot ask "who are all the tenants?" and it must not learn how.**
B1 / BR-TEN-013 forbid reading `tenancy.Tenant` from here, and tenancy publishes
no "every live tenant" selector — `dispatch_outbound` records exactly this and
therefore has no `--all-tenants` either. US-NOT-002 §1 wants a job **per
tenant** regardless, so that one utility's provider outage cannot delay
another's bills.

So the tenant list is OPERATOR CONFIGURATION: `NOTIFICATIONS_DISPATCH_TENANTS`,
a comma-separated list of subdomains. Set it and beat fires one dispatch per
tenant per interval.

⚠ **AND UNTIL 2026-09-03 THIS SECTION ENDED THERE, WITH: *"leave it unset and
beat fires the fan-out, which finds no tenants and says so on every firing
rather than looking healthy."* THAT SENTENCE WAS TRUE AND IT WAS ALSO THE LAST
DEAD LINK IN THE NOTIFICATION BELL (DEF-3422).** Nothing sets that variable —
not `docker-compose.yml`, not `.env.example`, not any deployment — so every
firing on every deployment paced NOBODY. The queue filled correctly, the
in-app adapter worked, the bell read the inbox, and no message ever crossed
between them. The Product Owner reported the end of the chain and not the
middle: *"this says - staff notification - but we dont get any notification"*.

**Hard-won law 3: the unsafe option must be the one you type.** Pacing no
utility is the unsafe option, so it is no longer what an unset variable means.
`scheduled_subdomains()` now falls back to every LIVE utility, through
`apps.tenancy.selectors.live_tenant_subdomains` — resolved BY NAME at call time
(BR-TEN-013), which is the day this file predicted and the one function it said
would change. B1 is intact: this module still cannot read `tenancy.Tenant` and
still does not. Configuration still WINS when it is set, so a deployment pacing
a deliberate subset loses nothing.

────────────────────────────────────────────────────────────────────────────
WHAT A FIRING ACTUALLY ACHIEVES ON THIS DEPLOYMENT
────────────────────────────────────────────────────────────────────────────
**In-app delivers.** Rows queued for the bell reach `sent` and land in
`in_app_messages`, which is the bell's own table — so a bill run's staff summary
appears without anybody running a command.

**Print, email and SMS do not, and that is the correct finished state, not a
backlog of failures.** `provider_seam.channel_route` refuses each with its own
reason (no adapter is published; email and SMS are deferred to W6 / v1.1) and
those reasons print on every firing. BR-NOT-013 is untouched: this schedule adds
no send path to any channel and cannot, because it calls the same one runner
that was already the only way in.
"""

from __future__ import annotations

import logging
import os
from importlib import import_module
from typing import Any

logger = logging.getLogger("smartbillhub.notifications.schedule")

#: The tenancy read that names every live utility — DEF-3422. Spelled once so
#: the contract is greppable from BOTH sides of the boundary, the way
#: `dispatch_outbound.py` spells `tenant_id_for_subdomain`.
TENANCY_MODULE = "tenancy"
TENANCY_READS = "selectors"
LIVE_TENANTS_READ = "live_tenant_subdomains"

#: The two routing names, pinned as literals for `apps/tenancy/tasks.py`'s own
#: reason: *"a renamed task is a message nobody consumes, and the queue says
#: nothing about it."* A module move must not orphan messages already in flight.
DISPATCH_TASK = "smartbillhub.notifications.dispatch_cycle"
FANOUT_TASK = "smartbillhub.notifications.dispatch_all"

#: The registered task objects, bound by `install()`. `None` means celery never
#: got hold of this module — see the ⚠ note inside `install()` for why the
#: return value of `app.task(...)` has to be kept rather than discarded.
_DISPATCH_ONE_TASK: Any = None
_DISPATCH_ALL_TASK: Any = None

#: The beat entry's own name. One key, so installing twice replaces rather than
#: duplicates — and two entries would be two cycles per interval, which is the
#: single-beat hazard `docker-compose.yml` warns about arriving by another door.
BEAT_ENTRY = "notifications.dispatch"

#: How often beat fires the fan-out. Seconds, because it is a DURATION.
DEFAULT_DISPATCH_EVERY_SECONDS = 300
DISPATCH_EVERY_SECONDS_ENV = "NOTIFICATIONS_DISPATCH_EVERY_SECONDS"

#: Comma-separated tenant subdomains this deployment paces. See the module
#: docstring for why this is configuration and not a query.
DISPATCH_TENANTS_ENV = "NOTIFICATIONS_DISPATCH_TENANTS"

#: What `dispatch_all` reports when nobody has configured a tenant. A sentence
#: an operator can act on, with no id and no code in it (CR-048's own rule about
#: refusals), because this one is read by whoever is wondering why the bell is
#: empty.
#: ⚠ AMENDED 2026-09-03 (DEF-3422). It used to read *"Add each utility's short
#: web address to the scheduled-sending setting on the server"*, which was the
#: right instruction while an operator's list was the ONLY source. It is not any
#: more — a firing with nothing configured now paces every live utility — so
#: this sentence is reached only when there are no live utilities to pace, or
#: when the read that names them could not be made. Telling an operator to fill
#: in a setting they do not need would have been the wrong instruction for the
#: one case that survives.
NO_TENANTS_CONFIGURED = (
    "No utility was found to send for, so nothing was dispatched. Messages are "
    "still being written and are waiting on the queue — none is lost. This is "
    "expected on a server with no utility set up yet; if there is one, name it "
    "in the scheduled-sending setting on the server."
)


def dispatch_every_seconds() -> int:
    """The interval, from configuration, with the default as the fallback.

    A value that is not a positive whole number is IGNORED with a log line
    rather than obeyed: a `0` or a `-1` would mean beat firing continuously,
    which is the burst BR-NOT-005 forbids arriving through a typo.
    """
    raw = os.environ.get(DISPATCH_EVERY_SECONDS_ENV, "").strip()
    if not raw:
        return DEFAULT_DISPATCH_EVERY_SECONDS
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        logger.warning(
            "%s=%r is not a positive number of seconds — the dispatch schedule "
            "is using its default of %s instead. A zero or negative interval "
            "would pace at no pace at all.",
            DISPATCH_EVERY_SECONDS_ENV,
            raw,
            DEFAULT_DISPATCH_EVERY_SECONDS,
        )
        return DEFAULT_DISPATCH_EVERY_SECONDS
    return seconds


def configured_subdomains() -> tuple[str, ...]:
    """The tenants an OPERATOR named, in the order they wrote them.

    De-duplicated, because the same subdomain twice would be two cycles per
    interval for one utility and none of the checks downstream would notice —
    each cycle claims its own batch legitimately.
    """
    raw = os.environ.get(DISPATCH_TENANTS_ENV, "")
    seen: list[str] = []
    for part in raw.split(","):
        subdomain = part.strip().lower()
        if subdomain and subdomain not in seen:
            seen.append(subdomain)
    return tuple(seen)


def _live_subdomains() -> tuple[str, ...] | None:
    """Every live utility, through tenancy's OWN published read, or None while
    it publishes none. BR-TEN-013: resolved by name at call time, so no import
    statement binds this module to tenancy's models."""
    try:
        target = import_module(f"apps.{TENANCY_MODULE}.{TENANCY_READS}")
    except ImportError:  # pragma: no cover — tenancy ships in this repo
        return None
    found = getattr(target, LIVE_TENANTS_READ, None)
    if not callable(found):
        return None
    try:
        listed = found()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception(
            "the live-utility read could not be made, so this firing paced "
            "nobody. Queued messages wait for the next one and nothing is lost."
        )
        return None
    seen: list[str] = []
    for entry in listed or ():
        subdomain = str(entry).strip().lower()
        if subdomain and subdomain not in seen:
            seen.append(subdomain)
    return tuple(seen)


def scheduled_subdomains() -> tuple[str, ...]:
    """The tenants this deployment paces. Configuration first, every live
    utility second.

    ⚠ **THIS FUNCTION RETURNED `()` ON EVERY DEPLOYMENT UNTIL 2026-09-03
    (DEF-3422), AND THE MODULE DOCSTRING DESCRIBED THAT AS THE HONEST SHAPE.**
    It was honest and it was also the last dead link in the notification bell:
    nothing sets `NOTIFICATIONS_DISPATCH_TENANTS`, so beat fired every five
    minutes, found no tenant, logged a sentence nobody reads and delivered
    nothing — while `outbound_messages` filled up correctly behind it. The
    Product Owner saw the consequence and not the cause: *"this says - staff
    notification - but we dont get any notification"*.

    **Hard-won law 3 says the unsafe option must be the one you type.** Pacing
    no utility at all is the unsafe option here, so it is no longer the default.
    An operator who names utilities still gets exactly those and no others —
    that is what the variable is for, and a deployment that wants to pace a
    subset has lost nothing.

    The module docstring's *"the tenant list is OPERATOR CONFIGURATION and not a
    query"* stands for the CONFIGURED case and is superseded for the empty one:
    B1 is not breached, because this module still does not read
    `tenancy.Tenant` — `apps.tenancy.selectors.live_tenant_subdomains` does, and
    is resolved BY NAME (BR-TEN-013), exactly as this file predicted it would
    be. While tenancy publishes no such read the old behaviour returns, with the
    same sentence on every firing.
    """
    configured = configured_subdomains()
    if configured:
        return configured
    return _live_subdomains() or ()


def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so it can be asserted in a
    test without starting celery — the schedule being *correct* and the schedule
    being *installed* are two different claims and hard-won law 2 is about
    exactly that gap.
    """
    return {
        BEAT_ENTRY: {
            "task": FANOUT_TASK,
            "schedule": float(
                every_seconds if every_seconds is not None else dispatch_every_seconds()
            ),
            # One firing = one cycle per tenant per channel. See the docstring.
            "args": (),
            "options": {"expires": None},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the schedule and the two tasks on the celery app. Idempotent.

    Called from `NotificationsConfig.ready()`. Returns what it did, so a caller
    (and a test) can tell "installed" from "celery is not importable here" —
    the two look identical from outside and only one of them is a problem.

    A failure to import celery is NOT an error: `manage.py check`, a migration
    and the test suite all run without a broker, and a Django app that refuses
    to start because a scheduler is absent would be a worse product than one
    whose queue drains a little later.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the notifications dispatch schedule was not installed: celery "
                "is not available here (%s). Nothing is broken — the queue "
                "still fills, and `manage.py dispatch_outbound` still drains it.",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    # Registered by NAME, so the routing name in `beat_schedule()` and the
    # registered task cannot drift — that drift is a message beat publishes and
    # no worker consumes, and the broker reports it as success.
    #
    # ⚠ THE RESULT IS KEPT, and that is not tidiness. `app.task(...)(fn)` returns
    # a NEW task object and leaves the module-level name bound to the plain
    # function, which has no `.delay`. A fan-out written as `dispatch_one.delay`
    # would therefore fall through to running every tenant's cycle INLINE inside
    # beat's own process — one utility's slow hand-off delaying every other
    # utility's bills, silently, with every test passing. The task objects are
    # bound here and `dispatch_all` reads them.
    global _DISPATCH_ONE_TASK, _DISPATCH_ALL_TASK
    _DISPATCH_ONE_TASK = app.task(name=DISPATCH_TASK, bind=False)(dispatch_one)
    _DISPATCH_ALL_TASK = app.task(name=FANOUT_TASK, bind=False)(dispatch_all)

    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


def dispatch_all() -> dict[str, Any]:
    """ONE firing: hand every configured tenant its own dispatch cycle.

    A fan-out and not a loop of cycles: each tenant's cycle is its own task, so
    one utility's slow hand-off cannot delay another's, which is the shape
    US-NOT-002 §1 asks for.

    Returns what it dispatched. Beat discards the value; the return exists so a
    test and an operator running this by hand see the same facts.
    """
    subdomains = scheduled_subdomains()
    if not subdomains:
        logger.warning("notifications dispatch schedule fired: %s", NO_TENANTS_CONFIGURED)
        return {"tenants": [], "dispatched": 0, "problem": NO_TENANTS_CONFIGURED}

    for subdomain in subdomains:
        try:
            if _DISPATCH_ONE_TASK is not None:
                _DISPATCH_ONE_TASK.delay(subdomain)
            else:
                # `install()` has not run (celery absent, or this was called
                # directly). Run it inline rather than silently doing nothing —
                # a fan-out that dispatches nowhere and reports success is the
                # shape DEF-320 was.
                dispatch_one(subdomain)
        except Exception:  # noqa: BLE001 — one tenant's broker error is not all of them
            logger.exception(
                "could not schedule the dispatch cycle for %s — its queued "
                "messages wait for the next firing and nothing is lost",
                subdomain,
            )
    return {"tenants": list(subdomains), "dispatched": len(subdomains), "problem": None}


def dispatch_one(subdomain: str, channels: tuple[str, ...] = ()) -> str:
    """ONE dispatch cycle for ONE tenant, through the runner that already exists.

    Everything this needs — resolving the subdomain through tenancy's own
    published read, naming the moment once, entering tenant context, refusing
    when the tenant is unknown — is `manage.py dispatch_outbound`'s and is not
    re-implemented here (see the module docstring).

    Returns the command's own report, so the reasons print in the worker log
    exactly as they print for an operator: which channels moved, and why the
    three that cannot did not.
    """
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    options: dict[str, Any] = {"tenant": subdomain, "stdout": out}
    if channels:
        options["channel"] = list(channels)
    call_command("dispatch_outbound", **options)
    report = out.getvalue().strip()
    logger.info("dispatch cycle for %s:\n%s", subdomain, report)
    return report


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B task B5 (12-governance/11-change-requests.md → CR-048 step 5 · 09-infra/01-deployment-architecture.md §4 "Celery beat … dispatcher pacing (NFR-1) … Run exactly one" and §10 item 3 "BEAT HAS NO SCHEDULE" · apps/notifications/dispatcher.py exception (7) · apps/notifications/management/commands/dispatch_outbound.py exceptions (1) and (2) · apps/tenancy/tasks.py, the one existing celery task and the shape this follows)
# generated: 2026-08-29 by story-coder (CR-048 wave B notifications lane) · AMENDED 2026-09-03 by story-coder (DEF-3422 bell lane — an unconfigured deployment paces every LIVE utility instead of none)
# checklist: A✔ B=deferred(no-API-half — a schedule is not a surface; the cycle it fires has no endpoint by BR-NOT-005) C✔ D=deferred(no-API-half, as above) E=deferred(no-frontend-half — nothing on a screen changes; what changes is that the bell fills without a command) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr048_b_engine_on.py · the schedule was proved RED before green (hard-won law 7): with `install()` not called from `ready()`, `app.conf.beat_schedule` held `{}` and the assertion read `assert {} != {}` / `KeyError: 'notifications.dispatch'`; with the entry present it names FANOUT_TASK and a 300-second interval. The END-TO-END proof is B4's: a bulk summary queued, no row in the bell, one firing, exactly one row in the bell.
# exceptions: (1) NO CLOCK IS READ HERE. beat owns the clock and this file owns an INTERVAL; the one instant a cycle needs is named by `dispatch_outbound`, which already did it. Stated because a scheduler is the one file where BR-TEN-043 looks inapplicable and is not.
#         (2) ⚠ SUPERSEDED 2026-09-03 (DEF-3422) AND KEPT AS THE RECORD. It read: "THE TENANT LIST IS OPERATOR CONFIGURATION, not a query — B1/BR-TEN-013 forbid reading `tenancy.Tenant` from here and tenancy publishes no live-tenant read … With the setting unset, every firing REPORTS that no utility is configured rather than looking healthy. REPORTED, and `scheduled_subdomains()` is the single function that changes when tenancy publishes one." Every word of that was true, and it meant that on every deployment — nothing sets the variable — the beat delivered NOTHING while the queue filled correctly behind it. Tenancy now publishes `selectors.live_tenant_subdomains`, `scheduled_subdomains()` is the single function that changed exactly as predicted, and B1 is intact because it is resolved BY NAME. Operator configuration still WINS when it is set; what changed is what an unset variable means (hard-won law 3 — the unsafe option must be the one you type).
#         (3) NOTHING NEW IS SENT. This adds no send path: it fires the one runner that was already the only way into `dispatch_cycle`. In-app delivers (BR-NOT-019); print, email and SMS rest `queued` with `provider_seam`'s own reasons on every firing (BR-NOT-013), which task B8's test asserts.
#         (4) A MISSING CELERY IS NOT AN ERROR. `install()` reports `installed: False` and the app starts. A Django app that refused to boot without a broker would be a worse product than one whose queue drains when the worker returns.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
