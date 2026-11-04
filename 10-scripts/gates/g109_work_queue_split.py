#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-030 (EP-WRK-05) — the push to the technician's phone.
#           `CR-070` wave J task J5, exit test: *"the push is a job on its own
#           queue with its consumer in the same commit (G59's shape, DEF-320)"*
# Rules:    BR-WRK-034 (assignment pushes the order to the phone) · B12 r1 §3
#           (async = a job row, then the broker message) · TD-17
# Defect:   DEF-320 (a queue nothing consumes: four job kinds enqueued, every
#           202 rested `queued` for ever) · DEF-338 (a worker's `command:`
#           became gunicorn's argv) · DEF-340 (`CMD` + `$HOSTNAME`)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove a guard
#           RED first) · DEF-182 (a check that cannot distinguish pass from fail)
# Tests:    selftest() below · 06-backend/tests/test_us_wrk_030_push.py
# ───────────────────────────────────────────────────────
"""G109 — the `work` queue must have BOTH halves, and they live in two files.

**This is `G59`'s shape, cloned for the queue wave J added**, and it reuses
`G59`'s compose reader rather than copying it: one reader, so a bug in it is a
bug in one place and `tests/test_cr051_billing_queue.py`'s real YAML parser
disagrees with both at once rather than with one.

WHY A THIRD NAMED QUEUE NEEDS ITS OWN GATE
------------------------------------------
`work.push` is registered to the `work` queue in `apps/work/push.py`
(`WorkConfig.ready()` calls `register()`), and `docker-compose.yml`'s
`celery-work` service consumes it. **Either half alone is worse than neither:**

  * **ROUTING with no CONSUMER** — every push is accepted, answers *queued*, and
    never runs. `core/jobs.py` names the shape in its own words: *"it accepts the
    file, says 'queued', and writes nothing, for ever."* That is `DEF-320`, which
    reached production across four job kinds.
  * **A CONSUMER with no ROUTING** — an idle container whose CPU limit bounds
    nothing at all, silently, for ever.

⚠ **AND THE FAILURE HERE IS QUIETER THAN BILLING'S, WHICH IS THE REASON THIS
GATE MATTERS MORE THAN IT LOOKS.** A bill run that never runs is noticed within a
day — nobody got a bill. A push that never fires is INVISIBLE: the technician's
phone still gets the job on its next ordinary sync, because the sync is the
delivery and the push is only the doorbell. The product looks correct and merely
feels slow, and no test, no log line and no screen would ever say so.

THE THIRD HALF, WHICH IS THE ONE PEOPLE LEAVE OUT
-------------------------------------------------
**No other worker may drain `work` as well.** `-Q celery,work` — which is
exactly what somebody types to "make sure nothing is missed" — restores every
problem the split was made to avoid while leaving the service, the queue and the
CPU limit all present and all pointless. `G59` states the same rule for billing
in the decision log's own words.

WHY IT FAILS RATHER THAN SKIPS
------------------------------
Every place it could fail to understand what it read reports **FAIL**. A gate
that cannot find the service it is checking has not verified anything, and this
repo keeps recording the opposite: `DEF-524`, a hardcoded path that outlived the
file it named and reported PASS through six UI defects.
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
PUSH = REPO / "06-backend" / "apps" / "work" / "push.py"
APPS = REPO / "06-backend" / "apps" / "work" / "apps.py"
ROUTER = REPO / "06-backend" / "config" / "celery_routes.py"

#: Only the fallback for an error message — the real value is read from
#: `push.py` at runtime, so renaming the queue there moves this gate with it.
EXPECTED_QUEUE = "work"


def findings() -> tuple[list[str], dict[str, object]]:
    problems: list[str] = []
    seen: dict[str, object] = {}

    if not COMPOSE.exists():
        return ([f"{COMPOSE.name} does not exist"], seen)
    services = g59._services(COMPOSE.read_text(encoding="utf-8"))
    if not services:
        return (["could not read any service out of docker-compose.yml"], seen)

    # ── the ROUTING half ────────────────────────────────────────────────────
    queue = EXPECTED_QUEUE
    if not PUSH.exists():
        problems.append(
            "06-backend/apps/work/push.py is missing — nothing declares the push job "
            "at all, so an assignment reaches no phone and no audit line says so"
        )
    else:
        text = PUSH.read_text(encoding="utf-8")
        match = re.search(r'^WORK_QUEUE = "([^"]+)"', text, re.M)
        if not match:
            problems.append(
                "apps/work/push.py declares no WORK_QUEUE — the push rides the shared "
                "queue, so it waits behind whatever a bill run is doing and the CPU "
                "limit on celery-work bounds nothing"
            )
        else:
            queue = match.group(1)
        if "set_job_queue" not in text:
            problems.append(
                "apps/work/push.py never calls core.jobs.set_job_queue — the queue has "
                "a NAME and nothing is routed to it"
            )
        if "set_job_handler" not in text:
            problems.append(
                "apps/work/push.py never calls core.jobs.set_job_handler — the kind is "
                "routed to a queue a worker drains, and the worker will find no BODY "
                "to run when it gets there"
            )
    seen["queue"] = queue

    if not APPS.exists() or "push.register()" not in APPS.read_text(encoding="utf-8"):
        problems.append(
            "apps/work/apps.py does not call push.register() in ready() — the handler "
            "and the queue are declared in a module nothing imports, so neither is "
            "registered in the web process or in the worker"
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
            f"NO service consumes the {queue!r} queue — every push is enqueued where "
            "nothing drains it (DEF-320: 'it accepts the file, says queued, and writes "
            "nothing, for ever'). It is INVISIBLE in this case: the phone still gets "
            "the job on its next ordinary sync, so the product merely feels slow"
        )
    dedicated = [name for name in consumers if workers[name] == [queue]]
    for name in consumers:
        if name in dedicated:
            continue
        problems.append(
            f"{name} drains {queue!r} ALONGSIDE {[one for one in workers[name] if one != queue]} "
            "— the split is cosmetic: a push waits behind whatever else that worker "
            "picked up, which is the whole thing a named queue exists to stop"
        )
    if len(dedicated) > 1:
        problems.append(
            f"{len(dedicated)} services are dedicated to {queue!r} "
            f"({', '.join(sorted(dedicated))}) — the CPU limit is PER CONTAINER, so the "
            "real share is silently their sum"
        )
    seen["dedicated"] = ", ".join(sorted(dedicated))

    # ── the work worker's own obligations — G59's clauses, same reasons ─────
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
                "of the machine the push worker may take"
            )
        elif not re.match(r"^\d+(\.\d+)?$", cpus) or float(cpus) <= 0:
            problems.append(f"{name}'s cpus limit {cpus!r} is not a positive number")
        if not replicas:
            problems.append(
                f"{name} has no `deploy.replicas` — 'scale on the fly' is a number "
                "somebody can change, and there is no number"
            )

    return problems, seen


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    ⚠ Both entry points on purpose — `DEF-672` (gates with `run()` and no
    `main()`, exiting 0 with no output) and `DEF-674` (`main()` and no `run()`,
    crashing inside the suite for weeks) are one convention with two halves, and
    a module can satisfy either alone and be dead in the other.

    ⚠ **AND `DEF-GOV-3733` IS WHY THIS MATTERS FOR THIS GATE IN PARTICULAR:**
    `G85` and `G87` were each shown red and then green through
    `python3 <gate>.py`, which exercises `__main__` and NEVER the path
    `run_gates` uses — both were announced green while the suite reported
    *"gate crashed: module has no attribute 'run'"*. So this gate's red proof was
    run through `run_gates.py`, not through this file.
    """
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"the {seen.get('queue')!r} queue is routed AND consumed: workers "
        f"{seen.get('workers')}, the push worker capped at {seen.get('cpus')} CPU × "
        f"{seen.get('replicas')} replica(s)",
    )


def main() -> int:
    status, note = run()
    print(f"G109 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
