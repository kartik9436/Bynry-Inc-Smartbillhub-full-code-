#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-051 task 29 (PO ruling 2026-08-31), verbatim: *"we will ahve to
#           create named worker for billing - eventually we should able to scale
#           these works on the fly itf required; but billing will need its own
#           named workers - otherwise it will slow down the system"*
# Defect:   DEF-320 (a queue nothing consumes: four job kinds enqueued, every
#           202 rested `queued` for ever) · DEF-338 (a worker's `command:`
#           became gunicorn's argv, so it restart-looped AND ran `migrate` every
#           restart) · DEF-340 (`CMD` + `$HOSTNAME`: no shell, and dash sets no
#           HOSTNAME either)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove a guard
#           RED first) · DEF-182 (a check whose output cannot distinguish pass
#           from fail is worse than no check)
# ───────────────────────────────────────────────────────
"""G59 — a NAMED QUEUE MUST HAVE BOTH HALVES, and they live in different files.

WHY THIS GATE EXISTS
--------------------
Billing has its own queue and its own worker as of 2026-08-31. That arrangement
is made of two statements in two different languages, and **either one alone is
worse than neither**:

  * **ROUTING** — `apps/billing/run_jobs.py` registers `billing.run.*` to the
    `billing` queue, and `config/settings/base.py` names the router that reads
    that registry. With no CONSUMER, a bill run is accepted, answers 202 and
    never runs. `core/jobs.py` names the shape in its own words: *"it accepts
    the file, says 'queued', and writes nothing, for ever."*
  * **A CONSUMER** — `docker-compose.yml`'s `celery-billing` service running
    `-Q billing`. With no ROUTING it is an idle container, and the CPU limit the
    Product Owner asked for applies to nothing at all, silently, for ever.

Nothing else in this repo can see either state. Every unit test passes on both;
every job still completes on the second; `docker ps` shows a healthy worker.

AND THE THIRD HALF, WHICH IS THE ONE PEOPLE LEAVE OUT
-----------------------------------------------------
**The default worker must not drain `billing` too.** The decision log states it
plainly: *"The default worker must STOP consuming billing, or the split is
cosmetic and the ordering harm remains."* `-Q celery,billing` — which is exactly
what somebody types to "make sure nothing is missed" — restores every problem the
split was ruled to fix, while leaving the new service, the new queue and the CPU
limit all present and all pointless.

WHAT ELSE IT CHECKS, AND WHY EACH ONE COST A DEPLOY
---------------------------------------------------
  * `entrypoint: []` on the billing worker (**DEF-338**). The image's ENTRYPOINT
    ends `exec gunicorn … "$@"`, so a bare `command:` becomes gunicorn's
    arguments: the container restart-loops, and everything above that exec line
    still runs — so a WORKER executes `manage.py migrate` and the reference-data
    sweep on every restart, against the database the web container migrates.
  * the healthcheck is `CMD-SHELL` with `$(hostname)` (**DEF-340**), never `CMD`
    with `$HOSTNAME`. The exec form runs no shell; and `CMD-SHELL` alone is not
    the fix either, because this image's `/bin/sh` is **dash**, which does not
    set `HOSTNAME` — the naive repair goes on failing for a second reason while
    looking fixed.
  * a CPU limit and a replica count exist on the billing worker — the two
    numbers the ruling actually asked for.
  * **`celery-beat` is at exactly one replica.** Its own margin says why: *"Beat
    is a clock, and two clocks do not conflict — they both fire."* It is checked
    HERE, in the gate about scaling workers, because the decision log says
    *"Whoever scales workers is the person who will scale this one too."*

WHY STDLIB ONLY, AND WHY IT FAILS RATHER THAN SKIPS
---------------------------------------------------
`run_gates.py` is Python 3.12 stdlib only, and PyYAML is not a declared
dependency of this repo. So the compose file is read with a small INDENTATION
reader rather than a YAML parser — and every place it could fail to understand
what it read, it reports **FAIL**, never PASS. A gate that cannot find the
service it is checking has not verified anything, and the one thing this repo
keeps recording is a check that reported success over a thing it never looked at
(DEF-524: a hardcoded path that outlived the file it named and reported PASS
through six UI defects).

`06-backend/tests/test_cr051_billing_queue.py` asserts the same facts with a real
YAML parser. The two agreeing is not redundancy — it is what says this reader is
reading the file correctly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
COMPOSE = REPO / "docker-compose.yml"
RUN_JOBS = REPO / "06-backend" / "apps" / "billing" / "run_jobs.py"
SETTINGS = REPO / "06-backend" / "config" / "settings" / "base.py"
ROUTER = REPO / "06-backend" / "config" / "celery_routes.py"

#: The queue billing's three job kinds ride. Read from `run_jobs.py` at runtime
#: (below) rather than trusted from here — this is only the fallback for the
#: error message when that read fails.
EXPECTED_QUEUE = "billing"


# ── a very small, very explicit compose reader ──────────────────────────────
def _services(text: str) -> dict[str, list[str]]:
    """`{service name: its block's lines}`, from the top-level `services:` map.

    Indentation only, no YAML. A service is a key at exactly two spaces under
    `services:`; its block is every line indented further, comments included —
    the comments are kept because a `#` line never satisfies any check below and
    dropping them would be one more thing that could go quietly wrong.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, one in enumerate(lines) if one.rstrip() == "services:")
    except StopIteration:
        return {}
    found: dict[str, list[str]] = {}
    name: str | None = None
    for one in lines[start + 1 :]:
        if one.strip() and not one.startswith(" "):
            break  # a new top-level key ends the services map
        match = re.match(r"^  ([A-Za-z0-9._-]+):\s*$", one)
        if match:
            name = match.group(1)
            found[name] = []
        elif name is not None:
            found[name].append(one)
    return found


def _flow_or_block_list(block: list[str], key: str) -> list[str] | None:
    """The value of `key:` in a service block, as a list of strings.

    Handles both forms this file uses: the flow list `command: ["a", "b"]`
    (valid JSON, so `json.loads` reads it exactly) and the block list under
    `command:` with `- "a"` items. Returns None when the key is absent, and an
    EMPTY LIST when it is present and empty (`entrypoint: []`) — the difference
    between those two is the whole of DEF-338, so they must not collapse.
    """
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
    """The `healthcheck.test` list — one level deeper than `command:`."""
    for line in block:
        match = re.match(r"^      test:\s*(.+)$", line)
        if match:
            try:
                return [str(one) for one in json.loads(match.group(1).strip())]
            except json.JSONDecodeError:
                return None
    return None


def _scalar(block: list[str], key: str) -> str | None:
    """The last non-comment scalar assigned to `key:` anywhere in the block."""
    found = None
    for line in block:
        match = re.match(rf"^\s+{re.escape(key)}:\s*(\S.*)$", line)
        if match and not line.lstrip().startswith("#"):
            found = match.group(1).strip().strip('"').strip("'")
    return found


def _queues(argv: list[str] | None) -> list[str] | None:
    """The queues a worker's argv says it consumes, or None if it is not a
    worker at all. A worker with no `-Q` consumes the DEFAULT queue — never
    "everything", which is the reading that would make this gate meaningless."""
    if not argv or "worker" not in argv:
        return None
    for flag in ("-Q", "--queues"):
        if flag in argv:
            index = argv.index(flag)
            if index + 1 >= len(argv):
                return []
            return [one for one in argv[index + 1].split(",") if one]
    return ["celery"]


def findings() -> tuple[list[str], dict[str, object]]:
    problems: list[str] = []
    seen: dict[str, object] = {}

    if not COMPOSE.exists():
        return ([f"{COMPOSE.relative_to(REPO)} does not exist"], seen)
    services = _services(COMPOSE.read_text(encoding="utf-8"))
    if not services:
        return (["could not read any service out of docker-compose.yml"], seen)
    seen["services"] = len(services)

    # ── the ROUTING half ────────────────────────────────────────────────────
    queue = EXPECTED_QUEUE
    if RUN_JOBS.exists():
        match = re.search(r'^BILLING_QUEUE = "([^"]+)"', RUN_JOBS.read_text(encoding="utf-8"), re.M)
        if not match:
            problems.append(
                "apps/billing/run_jobs.py declares no BILLING_QUEUE — billing's job "
                "kinds ride the shared queue, so a CPU cap on the billing worker "
                "bounds nothing"
            )
        else:
            queue = match.group(1)
    else:
        problems.append("06-backend/apps/billing/run_jobs.py is missing")
    seen["queue"] = queue

    if RUN_JOBS.exists() and "set_job_queue" not in RUN_JOBS.read_text(encoding="utf-8"):
        problems.append(
            "apps/billing/run_jobs.py never calls core.jobs.set_job_queue — the queue "
            "has a NAME and nothing is routed to it"
        )
    if not ROUTER.exists():
        problems.append("06-backend/config/celery_routes.py is missing — nothing routes")
    if SETTINGS.exists() and "CELERY_TASK_ROUTES" not in SETTINGS.read_text(encoding="utf-8"):
        problems.append(
            "config/settings/base.py sets no CELERY_TASK_ROUTES — the router module "
            "exists and Celery never consults it, so every bill run rides the "
            "default queue while the billing worker idles"
        )

    # ── the CONSUMER half, and the default worker that must not be one ─────
    workers = {
        name: _queues(_flow_or_block_list(block, "command")) for name, block in services.items()
    }
    workers = {name: qs for name, qs in workers.items() if qs is not None}
    if not workers:
        return (
            problems + ["no celery worker service found in docker-compose.yml at all"],
            seen,
        )
    seen["workers"] = {name: ",".join(qs) for name, qs in sorted(workers.items())}

    consumers = [name for name, qs in workers.items() if queue in qs]
    if not consumers:
        problems.append(
            f"NO service consumes the {queue!r} queue — every bill run is enqueued "
            "where nothing drains it (DEF-320: 'it accepts the file, says queued, "
            "and writes nothing, for ever')"
        )
    # A DEDICATED worker is one whose ONLY queue is billing's. Anything else that
    # lists the billing queue is draining it alongside other work, which is the
    # decision log's second constraint broken: *"The default worker must STOP
    # consuming billing, or the split is cosmetic and the ordering harm remains."*
    dedicated = [name for name in consumers if workers[name] == [queue]]
    for name in consumers:
        if name in dedicated:
            continue
        problems.append(
            f"{name} drains {queue!r} ALONGSIDE {[one for one in workers[name] if one != queue]} "
            "— the split is cosmetic: billing's CPU limit cannot bound work that an "
            "uncapped worker also picks up, and the ordering harm the PO ruled on "
            "remains"
        )
    if len(dedicated) > 1:
        problems.append(
            f"{len(dedicated)} services are dedicated to {queue!r} "
            f"({', '.join(sorted(dedicated))}) — the CPU limit is PER CONTAINER, so "
            "billing's real share is silently their sum"
        )
    seen["dedicated"] = ", ".join(sorted(dedicated))

    # ── the billing worker's own five obligations ──────────────────────────
    for name in dedicated:
        block = services[name]
        if _flow_or_block_list(block, "entrypoint") != []:
            problems.append(
                f"{name} does not clear its entrypoint (`entrypoint: []`) — its "
                "command becomes gunicorn's argv, so the container restart-loops AND "
                "runs `migrate` plus the reference-data sweep on every restart, "
                "against the database the web container migrates (DEF-338). A worker "
                "must never migrate."
            )
        test = _healthcheck_test(block)
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
                    "dash, which does not set it, so it expands to the empty string "
                    "and pings a node called 'celery@' for ever (DEF-340). Use "
                    "$(hostname)."
                )
            elif "hostname)" not in line:
                problems.append(
                    f"{name}'s healthcheck does not resolve its node name with "
                    "$(hostname) — it can only be pinging a node that does not exist"
                )
        cpus = _scalar(block, "cpus")
        replicas = _scalar(block, "replicas")
        seen["cpus"], seen["replicas"] = cpus, replicas
        if not cpus:
            problems.append(
                f"{name} has no `deploy.resources.limits.cpus` — nothing bounds how "
                "much of the machine a bill run takes, which is the state CR-051 "
                "task 28 measured (accounts list p95 605.8 ms idle → 2,868.9 ms "
                "under two runs)"
            )
        elif not re.match(r"^\d+(\.\d+)?$", cpus) or float(cpus) <= 0:
            problems.append(f"{name}'s cpus limit {cpus!r} is not a positive number")
        if not replicas:
            problems.append(
                f"{name} has no `deploy.replicas` — 'scale on the fly' is a number "
                "somebody can change, and there is no number"
            )

    # ── beat stays a single clock ──────────────────────────────────────────
    beat = next((name for name in services if "beat" in name), None)
    if beat is None:
        problems.append("no celery-beat service — a scheduler was ruled in on 2026-08-19")
    else:
        replicas = _scalar(services[beat], "replicas")
        seen["beat_replicas"] = replicas
        if replicas != "1":
            problems.append(
                f"{beat} runs {replicas!r} replicas, not 1 — two clocks do not "
                "conflict, they both fire: partition archival over the same range "
                "twice, report-retention DELETEs twice, and nothing logs a warning"
            )

    return problems, seen


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    ⚠ Both entry points on purpose — DEF-672 (sixteen gates with `run()` and no
    `main()`, exiting 0 with no output when run directly) and DEF-674 (`g41`
    with `main()` and no `run()`, crashing inside the suite for weeks) are one
    convention with two halves, and a module can satisfy either alone and be
    dead in the other. `main()` delegates here so the two cannot disagree.
    """
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"the {seen.get('queue')!r} queue is routed AND consumed: workers "
        f"{seen.get('workers')}, billing capped at {seen.get('cpus')} CPU × "
        f"{seen.get('replicas')} replica(s), beat at {seen.get('beat_replicas')}",
    )


def main() -> int:
    status, note = run()
    print(f"G59 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
