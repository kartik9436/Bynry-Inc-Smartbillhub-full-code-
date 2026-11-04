#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-007 (EP-RBS-03) — `CR-075` wave I task I1: the two job kinds
#           `runbooks.check` and `runbooks.act` on the existing platform runner,
#           with the queue they ride and the worker that drains it.
# Rules:    BR-INT-054 as amended 2026-09-06 (the SCHEDULER is Runbooks'; the
#           queue and the worker are the platform's and Runbooks rides them) ·
#           BR-RBS-016 (a schedule fires on the tenant's clock) · B12 r1 §3 ·
#           TD-17
# Defect:   DEF-320 (a queue nothing consumes: four job kinds enqueued, every
#           202 rested `queued` for ever) · DEF-338 (a worker's `command:`
#           became gunicorn's argv) · DEF-340 (`CMD` + `$HOSTNAME`) ·
#           DEF-RBS-4353 (the plan recorded this task as done and no code
#           implemented it — this gate is what would have said so)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove a guard
#           RED first, in the harness that will run it) · DEF-182
# Tests:    selftest() below · 06-backend/tests/test_us_rbs_007_scheduler.py
# ───────────────────────────────────────────────────────
"""G117 — the `runbooks` queue must have BOTH halves, and the beat must have an entry.

**This is `G59`'s shape, cloned for the fourth named queue**, and it reuses
`G59`'s compose reader rather than copying it — one reader, so a bug in it is a
bug in one place. `G109` did the same for `work`; the differences are below.

WHY A FOURTH NAMED QUEUE NEEDS ITS OWN GATE
-------------------------------------------
`runbooks.check` and `runbooks.act` are registered to the `runbooks` queue in
`apps/runbooks/scheduler.py` (`RunbooksConfig.ready()` calls `register()`), and
`docker-compose.yml`'s `celery-runbooks` service consumes it. **Either half
alone is worse than neither:**

  * **ROUTING with no CONSUMER** — every scheduled run is accepted, answers
    *queued*, and never runs. `core/jobs.py` names the shape in its own words:
    *"it accepts the file, says 'queued', and writes nothing, for ever."*
  * **A CONSUMER with no ROUTING** — an idle container whose CPU limit bounds
    nothing at all, silently, for ever.

⚠ **AND THIS MODULE'S FAILURE IS THE QUIETEST OF THE FOUR.** A bill run that
never runs is noticed within a day — nobody got a bill. A push that never fires
is invisible but the phone still syncs. **A scheduled Check that never runs
leaves NOTHING**: its entire output is a work list, and a work list that is
empty on a morning when it should not have been looks exactly like a good
morning. `EP-RBS-03`'s own words for the absence: *"an absence is invisible to
every check this repository has, and 'the sweep did not run for nine days' is
the kind of fact that is only ever discovered by the bill run failing."*

WHAT IS STRICTER HERE THAN IN `G109`
------------------------------------
**A THIRD CLAUSE: THE BEAT ENTRY.** The other three queues are fed by a person
pressing something. This one is fed by a clock, so there is a third half that
can be missing on its own: `apps/runbooks/scheduler.py` must declare a beat
entry AND `RunbooksConfig.ready()` must install it. Routing and a consumer with
no beat entry is a queue that is correctly plumbed and receives nothing, for
ever — and every screen goes on drawing *Next run · tomorrow 06:00*.

⚠ **THAT CLAUSE IS THE ONE THAT WOULD HAVE CAUGHT `DEF-RBS-4353`.** The
execution plan recorded task `I1` as ALREADY DONE while the two job-kind strings
existed in three documents and in zero Python files. Nothing compared a plan's
status word against the code, and nothing can — but this gate compares the
CODE's claim against the CODE, which is the half that is checkable.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY
---------------------------------------
Law 7's second habit, answered in writing.

  * **A worker that drains `runbooks` and something else.** Then the split is
    cosmetic: a 06:00 sweep waits behind a bill run. Checked — a consumer whose
    `-Q` list is not exactly `["runbooks"]` is a finding.
  * **Two dedicated workers.** The CPU limit is PER CONTAINER, so the real share
    is silently their sum. Checked.
  * **`register()` defined and never called.** The handler and the queue would
    be declared in a module nothing imports, so neither exists in the web
    process or in the worker. Checked against `apps/runbooks/apps.py`.
  * **A beat entry declared and never installed** — `beat_schedule()` returning
    a correct dict that `ready()` never passes to celery. That is hard-won law 2
    exactly, and it is why this gate reads `ready()` for `scheduler.install()`
    rather than trusting the function's existence.
  * **THE ONE IT CANNOT SEE, STATED RATHER THAN LEFT TO BE DISCOVERED:** it
    reads TEXT. It cannot tell whether the worker container actually starts,
    whether redis is reachable, or whether the sweep finds any tenant. Those are
    `10-scripts/11-smoke-stack.sh`'s and the walkthrough's, and this gate's PASS
    line says only what it checked.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The compose reader is G59's. Reused, not copied — see the module docstring.
import g59_billing_queue_split as g59  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
COMPOSE = REPO / "docker-compose.yml"
SCHEDULER = REPO / "06-backend" / "apps" / "runbooks" / "scheduler.py"
APPS = REPO / "06-backend" / "apps" / "runbooks" / "apps.py"
ROUTER = REPO / "06-backend" / "config" / "celery_routes.py"

#: Only the fallback for an error message — the real value is read from
#: `scheduler.py` at runtime, so renaming the queue there moves this gate too.
EXPECTED_QUEUE = "runbooks"

#: The two kinds `US-RBS-007` names. Membership matters, not the count: a kind
#: renamed on one side of the pair is a message nobody consumes.
EXPECTED_KINDS = ("runbooks.check", "runbooks.act")


def findings(compose_text: str | None = None) -> tuple[list[str], dict[str, object]]:
    """Every problem, and what was actually seen. `compose_text` is for selftest."""
    problems: list[str] = []
    seen: dict[str, object] = {}

    if compose_text is None:
        if not COMPOSE.exists():
            return ([f"{COMPOSE.name} does not exist"], seen)
        compose_text = COMPOSE.read_text(encoding="utf-8")
    services = g59._services(compose_text)
    if not services:
        return (["could not read any service out of docker-compose.yml"], seen)

    # ── the ROUTING half ────────────────────────────────────────────────────
    queue = EXPECTED_QUEUE
    if not SCHEDULER.exists():
        problems.append(
            "06-backend/apps/runbooks/scheduler.py is missing — nothing decides WHEN a "
            "runbook runs, so the product does nothing at all while the utility is "
            "asleep, which is the entire outcome EP-RBS-03 exists for"
        )
    else:
        text = SCHEDULER.read_text(encoding="utf-8")
        match = re.search(r'^RUNBOOKS_QUEUE = "([^"]+)"', text, re.M)
        if not match:
            problems.append(
                "apps/runbooks/scheduler.py declares no RUNBOOKS_QUEUE — a scheduled run "
                "rides the shared queue, so a ten-minute sweep over 40,000 accounts sits "
                "in front of whatever a clerk is waiting for"
            )
        else:
            queue = match.group(1)
        for kind in EXPECTED_KINDS:
            if f'"{kind}"' not in text:
                problems.append(
                    f"apps/runbooks/scheduler.py never names the job kind {kind!r} — "
                    "US-RBS-007 declares two kinds on the platform runner and this is "
                    "the file that owns them (DEF-RBS-4353: the plan said this was done "
                    "while the strings existed in three documents and no Python file)"
                )
        if "set_job_queue" not in text:
            problems.append(
                "apps/runbooks/scheduler.py never calls core.jobs.set_job_queue — the "
                "queue has a NAME and nothing is routed to it"
            )
        if "set_job_handler" not in text:
            problems.append(
                "apps/runbooks/scheduler.py never calls core.jobs.set_job_handler — the "
                "kind is routed to a queue a worker drains, and the worker will find no "
                "BODY to run when it gets there"
            )
        if "def beat_schedule" not in text:
            problems.append(
                "apps/runbooks/scheduler.py publishes no beat_schedule() — the queue is "
                "plumbed and nothing ever puts anything on it, while every screen goes "
                "on drawing a next-run time"
            )
    seen["queue"] = queue

    apps_text = APPS.read_text(encoding="utf-8") if APPS.exists() else ""
    if "scheduler.register()" not in apps_text:
        problems.append(
            "apps/runbooks/apps.py does not call scheduler.register() in ready() — the "
            "handler and the queue are declared in a module nothing imports, so neither "
            "is registered in the web process or in the worker"
        )
    if "scheduler.install()" not in apps_text:
        problems.append(
            "apps/runbooks/apps.py does not call scheduler.install() in ready() — the "
            "beat entry is a correct dict nobody hands to celery, which is hard-won "
            "law 2 with a clock in it: nothing fires and nothing says so"
        )
    if not ROUTER.exists():
        problems.append("06-backend/config/celery_routes.py is missing — nothing routes")

    # ── the CONSUMER half, and every other worker that must not be one ──────
    workers = {
        name: g59._queues(g59._flow_or_block_list(block, "command"))
        for name, block in services.items()
    }
    workers = {name: qs for name, qs in workers.items() if qs is not None}
    if not workers:
        return (problems + ["no celery worker service found in docker-compose.yml at all"], seen)
    seen["workers"] = {name: ",".join(qs) for name, qs in sorted(workers.items())}

    consumers = [name for name, qs in workers.items() if queue in qs]
    if not consumers:
        problems.append(
            f"NO service consumes the {queue!r} queue — every scheduled run is enqueued "
            "where nothing drains it (DEF-320). It is the QUIETEST of the four: a Check "
            "that never runs leaves an empty work list, which looks exactly like a good "
            "morning"
        )
    dedicated = [name for name in consumers if workers[name] == [queue]]
    for name in consumers:
        if name in dedicated:
            continue
        problems.append(
            f"{name} drains {queue!r} ALONGSIDE {[one for one in workers[name] if one != queue]} "
            "— the split is cosmetic: a sweep waits behind whatever else that worker "
            "picked up, which is the whole thing a named queue exists to stop"
        )
    if len(dedicated) > 1:
        problems.append(
            f"{len(dedicated)} services are dedicated to {queue!r} "
            f"({', '.join(sorted(dedicated))}) — the CPU limit is PER CONTAINER, so the "
            "real share is silently their sum"
        )
    seen["dedicated"] = ", ".join(sorted(dedicated))

    # ── the runbooks worker's own obligations — G59's clauses, same reasons ─
    for name in dedicated:
        block = services[name]
        if g59._flow_or_block_list(block, "entrypoint") != []:
            problems.append(
                f"{name} does not clear its entrypoint (`entrypoint: []`) — its command "
                "becomes gunicorn's argv, so the container restart-loops AND runs "
                "`migrate` plus the reference-data sweep on every restart, against the "
                "database the web container migrates (DEF-338). A worker must never "
                "migrate."
            )
        test = g59._healthcheck_test(block)
        if not test:
            problems.append(f"{name} has no readable healthcheck.test")
        else:
            if test[0] != "CMD-SHELL":
                problems.append(
                    f"{name}'s healthcheck is {test[0]!r}, not 'CMD-SHELL' — the exec "
                    "form runs no shell, so nothing expands a command substitution "
                    "(DEF-340)"
                )
            line = " ".join(test[1:])
            if "$HOSTNAME" in line.replace("$$", "$"):
                problems.append(
                    f"{name}'s healthcheck uses $HOSTNAME — this image's /bin/sh is "
                    "dash, which does not set it, so it expands to the empty string and "
                    "pings a node called 'celery@' for ever (DEF-340). Use $(hostname)."
                )
            elif "hostname)" not in line:
                problems.append(
                    f"{name}'s healthcheck does not resolve its node name with "
                    "$(hostname) — it can only be pinging a node that does not exist"
                )
        cpus = g59._scalar(block, "cpus")
        replicas = g59._scalar(block, "replicas")
        seen["cpus"], seen["replicas"] = cpus, replicas
        if not cpus:
            problems.append(
                f"{name} has no `deploy.resources.limits.cpus` — nothing bounds how much "
                "of the machine an unattended runbook run may take, and this is the one "
                "of the four queues that can actually saturate a core"
            )
        elif not re.match(r"^\d+(\.\d+)?$", cpus) or float(cpus) <= 0:
            problems.append(f"{name}'s cpus limit {cpus!r} is not a positive number")
        if not replicas:
            problems.append(
                f"{name} has no `deploy.replicas` — 'scale on the fly' is a number "
                "somebody can change, and there is no number"
            )

    return problems, seen


def selftest() -> int:
    """Prove the gate can FAIL, on the two mutations that matter.

    ⚠ A selftest is not the red proof law 7 asks for — that was run through
    `run_gates.py` against the real tree with the consumer renamed away, and the
    failure text is quoted in the wave's decision-log row. This is the cheap
    repeatable half, so a later lane refactoring the compose reader finds out.
    """
    real = COMPOSE.read_text(encoding="utf-8")
    problems, _ = findings(real)
    if problems:
        print("SELFTEST FAIL — the real tree should pass:", problems)
        return 1

    renamed = real.replace("  celery-runbooks:\n", "  celery-runbooks-disabled:\n").replace(
        '"-Q", "runbooks"', '"-Q", "celery"'
    )
    problems, _ = findings(renamed)
    if not any("NO service consumes" in one for one in problems):
        print("SELFTEST FAIL — a tree with no consumer was not caught:", problems)
        return 1

    shared = real.replace(
        '"worker", "-Q", "runbooks", "--loglevel"',
        '"worker", "-Q", "runbooks,celery", "--loglevel"',
    )
    problems, _ = findings(shared)
    if not any("ALONGSIDE" in one for one in problems):
        print("SELFTEST FAIL — a shared worker was not caught:", problems)
        return 1

    print("SELFTEST PASS — the real tree passes; no-consumer and shared-worker both fail")
    return 0


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    ⚠ Both entry points on purpose — `DEF-672` and `DEF-674` are one convention
    with two halves, and `DEF-GOV-3733` is why the red proof for this gate was
    run through `run_gates.py` rather than through `python3 g117_….py`: that
    path exercises `__main__` and never this function.
    """
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"the {seen.get('queue')!r} queue is routed, consumed and fed by a beat entry: "
        f"workers {seen.get('workers')}, the runbooks worker capped at {seen.get('cpus')} "
        f"CPU × {seen.get('replicas')} replica(s). It does NOT check that the container "
        f"starts or that the sweep finds a tenant — that is the smoke stack's",
    )


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    status, note = run()
    print(f"G117 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
