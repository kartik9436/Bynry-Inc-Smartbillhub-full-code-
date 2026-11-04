#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-016 (EP-INT-05) TC-2 — the `integrations` queue has BOTH
#           halves: routing in `apps/integrations/jobs.py` and a consumer in
#           `docker-compose.yml`; the default worker does not drain it.
# Rules:    BR-INT-041 (P5 — its own named queue WITH its own consuming
#           worker; a route with no consumer accepts work and never runs) ·
#           DEF-320 · DEF-338 · DEF-340 · CLAUDE.md hard-won law 2 (built is
#           not wired) · law 7 (proven RED first — see the docstring)
# Tests:    06-backend/tests/test_us_int_016_queue.py (runs `findings()` on a
#           compose text with the service renamed away and with the default
#           worker draining the queue) · selftest() below
# Impacts:  docker-compose.yml · 06-backend/apps/integrations/jobs.py
# ───────────────────────────────────────────────────────
"""G80 — the `integrations` queue must have both halves, and the default worker must not be one.

G59's clauses, cloned for the second named queue — because the failure
shape is the same and the two queues are two files apart:

  * ROUTING — `apps/integrations/jobs.py` declares `INTEGRATIONS_QUEUE` and
    calls `core.jobs.set_job_queue` for every kind; `config/celery_routes.py`
    and `CELERY_TASK_ROUTES` already exist (G59 checks those). With no
    CONSUMER, a test request is accepted, answers 202 and never runs —
    `core/jobs.py`'s own words: *"it accepts the file, says 'queued', and
    writes nothing, for ever."*
  * A CONSUMER — `docker-compose.yml`'s `celery-integrations` on
    `-Q integrations`, and ONLY that queue. With no ROUTING it is an idle
    container.
  * THE THIRD HALF — the default worker (`-Q celery`) and the billing worker
    must NOT list `integrations` too. `-Q celery,integrations` is exactly
    what somebody types to "make sure nothing is missed", and it puts a
    hanging mail server back on the worker that answers the clerk.
  * the worker's own obligations: `entrypoint: []` (DEF-338 — a worker must
    never migrate), a `CMD-SHELL` healthcheck with `$(hostname)` (DEF-340),
    a CPU limit and a replica count.

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With the worker's `-Q integrations` changed to `-Q elsewhere` in a copy of
the compose file the gate reported *NO service consumes the 'integrations'
queue* (renaming the SERVICE is not a sabotage — a consumer under another
name still consumes, and the gate was right to stay green on that); with the default
worker's command changed to `-Q celery,integrations` it reported *celery
drains 'integrations' ALONGSIDE ['celery']*. `selftest()` replays both on an
in-memory compose text and `run()` refuses to report anything until it has.

Stdlib only — the same indentation reader as G59, and every place it could
fail to understand what it read reports FAIL, never PASS (DEF-524's lesson).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
COMPOSE = REPO / "docker-compose.yml"
JOBS = REPO / "06-backend" / "apps" / "integrations" / "jobs.py"

EXPECTED_QUEUE = "integrations"


# ── the compose reader — G59's, verbatim in behaviour ───────────────────────
def _services(text: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    try:
        start = next(i for i, one in enumerate(lines) if one.rstrip() == "services:")
    except StopIteration:
        return {}
    found: dict[str, list[str]] = {}
    name: str | None = None
    for one in lines[start + 1 :]:
        if one.strip() and not one.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9._-]+):\s*$", one)
        if match:
            name = match.group(1)
            found[name] = []
        elif name is not None:
            found[name].append(one)
    return found


def _flow_or_block_list(block: list[str], key: str) -> list[str] | None:
    pattern = re.compile(rf"^    {re.escape(key)}:\s*(.*)$")
    for index, line in enumerate(block):
        match = pattern.match(line)
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            try:
                return [str(one) for one in json.loads(inline)]
            except json.JSONDecodeError:
                return None
        items: list[str] = []
        for following in block[index + 1 :]:
            if re.match(r"^      - ", following):
                items.append(following.split("- ", 1)[1].strip().strip('"').strip("'"))
            elif following.strip() and not following.startswith("       "):
                break
        return items
    return None


def _healthcheck_test(block: list[str]) -> list[str] | None:
    for line in block:
        match = re.match(r"^      test:\s*(.+)$", line)
        if match:
            try:
                return [str(one) for one in json.loads(match.group(1).strip())]
            except json.JSONDecodeError:
                return None
    return None


def _scalar(block: list[str], key: str) -> str | None:
    found = None
    for line in block:
        match = re.match(rf"^\s+{re.escape(key)}:\s*(\S.*)$", line)
        if match and not line.lstrip().startswith("#"):
            found = match.group(1).strip().strip('"').strip("'")
    return found


def _queues(argv: list[str] | None) -> list[str] | None:
    if not argv or "worker" not in argv:
        return None
    for flag in ("-Q", "--queues"):
        if flag in argv:
            index = argv.index(flag)
            if index + 1 >= len(argv):
                return []
            return [one for one in argv[index + 1].split(",") if one]
    return ["celery"]


def findings(compose_text: str | None = None, jobs_text: str | None = None) -> tuple[list[str], dict[str, object]]:
    """`(problems, seen)`. Both texts are injectable so the tests and the
    self-test can sabotage a COPY; the real files are read when None."""
    problems: list[str] = []
    seen: dict[str, object] = {}

    if compose_text is None:
        if not COMPOSE.exists():
            return ([f"{COMPOSE.relative_to(REPO)} does not exist"], seen)
        compose_text = COMPOSE.read_text(encoding="utf-8")
    if jobs_text is None:
        if not JOBS.exists():
            return (["06-backend/apps/integrations/jobs.py is missing — nothing routes"], seen)
        jobs_text = JOBS.read_text(encoding="utf-8")

    services = _services(compose_text)
    if not services:
        return (["could not read any service out of docker-compose.yml"], seen)
    seen["services"] = len(services)

    # ── the ROUTING half ────────────────────────────────────────────────────
    match = re.search(r'^INTEGRATIONS_QUEUE = "([^"]+)"', jobs_text, re.M)
    queue = match.group(1) if match else EXPECTED_QUEUE
    if not match:
        problems.append(
            "apps/integrations/jobs.py declares no INTEGRATIONS_QUEUE — the kinds ride the "
            "shared queue, so a hanging mail server holds the worker that answers the clerk"
        )
    if "set_job_queue" not in jobs_text:
        problems.append(
            "apps/integrations/jobs.py never calls core.jobs.set_job_queue — the queue has a "
            "NAME and nothing is routed to it"
        )
    seen["queue"] = queue

    # ── the CONSUMER half, and the workers that must not be one ────────────
    workers = {name: _queues(_flow_or_block_list(block, "command")) for name, block in services.items()}
    workers = {name: qs for name, qs in workers.items() if qs is not None}
    if not workers:
        return (problems + ["no celery worker service found in docker-compose.yml at all"], seen)
    seen["workers"] = {name: ",".join(qs) for name, qs in sorted(workers.items())}

    consumers = [name for name, qs in workers.items() if queue in qs]
    if not consumers:
        problems.append(
            f"NO service consumes the {queue!r} queue — every test request is enqueued where "
            "nothing drains it (DEF-320: 'it accepts the file, says queued, and writes "
            "nothing, for ever')"
        )
    dedicated = [name for name in consumers if workers[name] == [queue]]
    for name in consumers:
        if name in dedicated:
            continue
        problems.append(
            f"{name} drains {queue!r} ALONGSIDE {[one for one in workers[name] if one != queue]} "
            "— the split is cosmetic: a hanging provider on this worker holds the other work "
            "it drains, which is the outage P5 exists to prevent (BR-INT-041)"
        )
    if len(dedicated) > 1:
        problems.append(
            f"{len(dedicated)} services are dedicated to {queue!r} ({', '.join(sorted(dedicated))}) "
            "— the CPU limit is PER CONTAINER, so the real share is silently their sum"
        )
    seen["dedicated"] = ", ".join(sorted(dedicated))

    # ── the worker's own obligations (DEF-338 · DEF-340 · the two numbers) ──
    for name in dedicated:
        block = services[name]
        if _flow_or_block_list(block, "entrypoint") != []:
            problems.append(
                f"{name} does not clear its entrypoint (`entrypoint: []`) — its command becomes "
                "gunicorn's argv, the container restart-loops AND runs `migrate` on every "
                "restart (DEF-338). A worker must never migrate."
            )
        test = _healthcheck_test(block)
        if not test:
            problems.append(f"{name} has no readable healthcheck.test")
        else:
            if test[0] != "CMD-SHELL":
                problems.append(f"{name}'s healthcheck is {test[0]!r}, not 'CMD-SHELL' (DEF-340)")
            line = " ".join(test[1:])
            if "$HOSTNAME" in line.replace("$$", "$"):
                problems.append(f"{name}'s healthcheck uses $HOSTNAME — dash sets no HOSTNAME (DEF-340); use $(hostname)")
            elif "hostname)" not in line:
                problems.append(f"{name}'s healthcheck does not resolve its node name with $(hostname)")
        cpus = _scalar(block, "cpus")
        replicas = _scalar(block, "replicas")
        seen["cpus"], seen["replicas"] = cpus, replicas
        if not cpus:
            problems.append(f"{name} has no `deploy.resources.limits.cpus` — nothing bounds it")
        elif not re.match(r"^\d+(\.\d+)?$", cpus) or float(cpus) <= 0:
            problems.append(f"{name}'s cpus limit {cpus!r} is not a positive number")
        if not replicas:
            problems.append(f"{name} has no `deploy.replicas` — 'scale on the fly' is a number, and there is no number")

    return problems, seen


# ── the self-test: both sabotages must bite on an in-memory copy ────────────
_CLEAN = """services:
  celery:
    entrypoint: []
    command: ["celery", "-A", "config.celery", "worker", "-Q", "celery"]
  celery-billing:
    entrypoint: []
    command: ["celery", "-A", "config.celery", "worker", "-Q", "billing"]
  celery-integrations:
    entrypoint: []
    command: ["celery", "-A", "config.celery", "worker", "-Q", "integrations"]
    deploy:
      resources:
        limits:
          cpus: "0.5"
      replicas: 1
    healthcheck:
      test: ["CMD-SHELL", "celery -A config.celery inspect ping -d celery@$$(hostname)"]
"""
_JOBS = 'INTEGRATIONS_QUEUE = "integrations"\ncore_jobs.set_job_queue(kind, INTEGRATIONS_QUEUE)\n'


def selftest() -> bool:
    clean, _ = findings(compose_text=_CLEAN, jobs_text=_JOBS)
    if clean:
        return False
    gone, _ = findings(compose_text=_CLEAN.replace('"-Q", "integrations"]', '"-Q", "elsewhere"]'), jobs_text=_JOBS)
    greedy, _ = findings(compose_text=_CLEAN.replace('"-Q", "celery"]', '"-Q", "celery,integrations"]'), jobs_text=_JOBS)
    unrouted, _ = findings(compose_text=_CLEAN, jobs_text="# nothing declared\n")
    return (
        any("NO service consumes the 'integrations' queue" in one for one in gone)
        and any("drains 'integrations' ALONGSIDE" in one for one in greedy)
        and any("declares no INTEGRATIONS_QUEUE" in one for one in unrouted)
    )


def run() -> tuple[str, str]:
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a consumed queue from an "
            "unconsumed one, so its verdict is worthless (DEF-182)"
        )
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"the {seen.get('queue')!r} queue is routed AND consumed by {seen.get('dedicated')} alone: "
        f"workers {seen.get('workers')}, capped at {seen.get('cpus')} CPU × {seen.get('replicas')} "
        "replica(s); self-test: all three sabotages bite",
    )


def main() -> int:
    status, note = run()
    print(f"G80 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
