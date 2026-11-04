# ── Trace ──────────────────────────────────────────────
# Component: CR-051 task 29 — billing's NAMED queue and its dedicated worker.
# Change:   PO ruling 2026-08-31, verbatim: *"we will ahve to create named worker
#           for billing - eventually we should able to scale these works on the
#           fly itf required; but billing will need its own named workers -
#           otherwise it will slow down the system"*
#           (12-governance/02-decision-log.md).
# Defect:   DEF-320 (four job kinds enqueued and nothing consumed them — the
#           shape a route with no consumer recreates exactly) · DEF-338 (a
#           worker's `command:` became gunicorn's argv, so it restart-looped AND
#           ran `migrate` on every restart) · DEF-340 (`CMD` + `$HOSTNAME` in a
#           healthcheck: no shell, and dash sets no HOSTNAME either)
# Contract: TD-17 (async = Celery on Redis) · B12 r1 §3 (202 + job_id)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove a guard
#           RED first) · law 3 (defaults fail closed)
# Tests:    this file · 10-scripts/gates/g59_billing_queue_split.py (the same
#           facts as a merge gate) · 10-scripts/cr051_billing_worker_cap.py (the
#           re-measurement the ruling asks for)
# Impacts:  config/celery_routes.py · config/settings/base.py · core/jobs.py ·
#           apps/billing/run_jobs.py · apps/tenancy/tasks.py ·
#           apps/tenancy/services.py · docker-compose.yml
# ───────────────────────────────────────────────────────
"""A named queue is TWO halves, and each half fails differently. Test both.

**WHY THAT SENTENCE IS THE WHOLE DESIGN OF THIS MODULE.** The decision log's
first constraint reads: *"A named queue needs BOTH halves — routing AND a worker
consuming it. Ship one without the other and a job is enqueued to a queue nothing
drains."* The two halves live in different files, in different languages, and
they fail in opposite directions:

* **routing without a consumer** — a bill run is accepted, answers 202, and never
  runs. `core/jobs.py` names this shape in its own words: *"it accepts the file,
  says 'queued', and writes nothing, for ever."* This is the dangerous half.
* **a consumer without routing** — an idle container. Nothing breaks; the CPU cap
  the PO asked for simply applies to nothing, silently, for ever. This is the
  half nobody notices.

So the cases below break them SEPARATELY and assert different failures, because
a single test that could not tell them apart would be a check that cannot fail
(DEF-182 — this repo has recorded six of those in one day).

⚠ **WHAT THIS FILE CANNOT PROVE, said plainly rather than implied.** It runs in
ONE process. It cannot prove a real `celery worker -Q billing` consumes a real
Redis queue — that needs three processes, and `10-scripts/verify_celery_transport.py`
is the script that does it. What it CAN prove is that Celery's **own router** —
the same `app.amqp.router` that `.delay()` consults — sends a billing message to
the `billing` queue and a non-billing message to the default one, and that the
compose file names a service consuming exactly that queue. Everything below is
one of those two.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml
from django.conf import settings

from apps.billing import run_jobs
from config import celery_routes
from core import jobs as core_jobs

REPO = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = REPO / "docker-compose.yml"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _queues_of(service: dict) -> list[str]:
    """The queue names a service's `command:` says it consumes.

    Read from the argv rather than by grepping the file: `-Q billing` and a
    comment mentioning "billing" are different facts, and only one of them is a
    consumer. A worker with no `-Q` at all consumes the default queue, which is
    what every worker in this repo did before 2026-08-31 — so an empty flag
    means `[CELERY_TASK_DEFAULT_QUEUE]`, never "all of them".
    """
    argv = list(service.get("command") or [])
    if "worker" not in argv:
        return []
    for flag in ("-Q", "--queues"):
        if flag in argv:
            return [one.strip() for one in argv[argv.index(flag) + 1].split(",") if one.strip()]
    return [settings.CELERY_TASK_DEFAULT_QUEUE]


def _routed_queue(route) -> str | None:
    """The queue NAME a router result names.

    ⚠ `app.amqp.router.route()` does not return the string you put in
    `task_routes`. It resolves the name against the app's known queues and hands
    back a **kombu `Queue` object**, so `route["queue"] == "billing"` is False
    over a router that is working perfectly — which is what the first run of
    these cases asserted, and it read exactly like a broken split. Compare the
    NAME, and let a plain string through for the case where nothing resolved it.
    """
    if not route or "queue" not in route:
        return None
    queue = route["queue"]
    return getattr(queue, "name", None) or str(queue)


# ── 1 · THE ROUTING HALF, through Celery's own router ───────────────────────
def test_cr051_q1__a_bill_run_message_routes_to_the_billing_queue():
    """RED-PROVED by REMOVING THE ROUTING, two different ways, both of which a
    real edit could produce:

      * deleting the `for kind in RUN_JOBS: set_job_queue(...)` loop from
        `apps/billing/run_jobs.register()`:
            AssertionError: billing.run.calculate went to the 'celery' queue,
            not 'billing' — the routing half is missing …
      * deleting `CELERY_TASK_ROUTES` from `config/settings/base.py`:
            AssertionError: billing.run.calculate went to the 'celery' queue …

    Both are the SAME assertion because both produce the same fault — a bill run
    on the shared queue — and that is exactly right: the test is about the
    outcome, not about which of the two lines was cut.

    ⚠ **IT ASKS `app.amqp.router`, WHICH IS WHAT `.delay()` ASKS.** A test that
    called `celery_routes.route_job` directly would pass with `task_routes`
    unset, over a product where nothing is routed anywhere.
    """
    from config.celery import app as celery_app

    for kind in run_jobs.RUN_JOBS:
        route = celery_app.amqp.router.route(
            {},
            celery_routes.RUN_PENDING_TASK,
            ("job-id", "tenant-id"),
            {"kind": kind},
        )
        assert _routed_queue(route) == run_jobs.BILLING_QUEUE, (
            f"{kind} went to the {_routed_queue(route)!r} queue, not "
            f"{run_jobs.BILLING_QUEUE!r} — the routing half is missing, so the "
            "billing worker idles and its CPU cap applies to nothing"
        )


def test_cr051_q2__a_non_billing_job_still_rides_the_default_queue():
    """The split must not sweep everything onto the new queue.

    RED-PROVED by registering the default queue for a non-billing kind
    (`core_jobs.set_job_queue("audit_export", "billing")`):
        AssertionError: audit_export was routed to 'billing' — a CSV export
        must stay on the default queue …

    This is the case that keeps the change HONEST: the PO asked for billing to be
    separable, and a change that moved exports and notices too would cap them
    with the same number and answer a question nobody asked.
    """
    from config.celery import app as celery_app

    route = celery_app.amqp.router.route(
        {},
        celery_routes.RUN_PENDING_TASK,
        ("job-id", "tenant-id"),
        {"kind": "audit_export"},
    )
    queue = _routed_queue(route) or settings.CELERY_TASK_DEFAULT_QUEUE
    assert queue != run_jobs.BILLING_QUEUE, (
        f"audit_export was routed to {queue!r} — a CSV export must stay on the "
        "default queue, or capping billing caps the exports too, which is the "
        "state this change exists to leave"
    )


def test_cr051_q3__the_kind_reaches_the_message_as_a_keyword():
    """The router reads the kind out of the message's KWARGS. Passed
    positionally it would still reach the body, the job would run, and every
    bill run would quietly ride the default queue for ever.

    RED-PROVED by changing `send()` to pass the kind positionally:
        AssertionError: the kind never reached the message kwargs …
    and note what does NOT happen in that state: no error, no failed job, no log
    line. That is why this case exists separately from Q1.
    """
    from apps.tenancy import tasks as tenancy_tasks

    seen: list[tuple[tuple, dict]] = []

    class _Fake:
        def delay(self, *args, **kwargs):
            seen.append((args, kwargs))

    real = tenancy_tasks.run_pending_job
    tenancy_tasks.run_pending_job = _Fake()  # type: ignore[assignment]
    try:
        tenancy_tasks.send({"id": "job-1", "tenant_id": "tenant-1", "kind": run_jobs.CALCULATE_JOB})
    finally:
        tenancy_tasks.run_pending_job = real  # type: ignore[assignment]

    assert seen, "send() dispatched nothing"
    args, kwargs = seen[0]
    assert kwargs.get("kind") == run_jobs.CALCULATE_JOB, (
        "the kind never reached the message kwargs — the router would see an "
        f"empty kwargs dict and route every bill run to the default queue. Got "
        f"args={args!r} kwargs={kwargs!r}"
    )
    assert args == (
        "job-1",
        "tenant-1",
    ), "the positional pair the worker actually reads must not have moved"


# ── 2 · THE CONSUMER HALF, read out of docker-compose.yml ───────────────────
def test_cr051_q4__a_service_consumes_the_billing_queue():
    """RED-PROVED by deleting the `celery-billing` service from
    `docker-compose.yml`:
        AssertionError: NO service consumes the 'billing' queue — every bill run
        would be enqueued where nothing drains it …

    and RED-PROVED a second, subtler way, by removing only its `-Q billing`
    (leaving the service): the worker falls back to the default queue and this
    still fails with the same sentence. **That second proof is the one worth
    having** — a service that exists and consumes the wrong queue looks entirely
    healthy in `docker ps`.
    """
    services = _compose()["services"]
    consumers = [name for name, svc in services.items() if "billing" in _queues_of(svc)]
    assert consumers, (
        "NO service consumes the 'billing' queue — every bill run would be "
        "enqueued where nothing drains it, which core/jobs.py calls 'it accepts "
        "the file, says queued, and writes nothing, for ever' (DEF-320)"
    )


def test_cr051_q5__the_default_worker_no_longer_drains_billing():
    """The half that is easiest to leave out and impossible to see afterwards.

    RED-PROVED by adding `billing` back to the `celery` service's `-Q` list
    (`-Q celery,billing`, which is exactly what somebody would type to "make
    sure nothing is missed"):
        AssertionError: the default worker 'celery' still drains ['celery',
        'billing'] — the split is cosmetic …

    Nothing else in the repo can see that state: the billing worker still runs,
    the routing still routes, every job still completes, and the CPU cap still
    exists — it just no longer bounds how much machine billing takes, because
    the uncapped default worker picks the runs up too.
    """
    services = _compose()["services"]
    default_workers = {
        name: _queues_of(svc)
        for name, svc in services.items()
        if _queues_of(svc) and "billing" not in name
    }
    offenders = {name: qs for name, qs in default_workers.items() if "billing" in qs}
    assert not offenders, (
        f"the default worker(s) {sorted(offenders)} still drain "
        f"{[qs for qs in offenders.values()]} — the split is cosmetic and the "
        "ordering harm the PO ruled on remains"
    )


def test_cr051_q6__the_billing_worker_clears_its_entrypoint_and_never_migrates():
    """DEF-338, and it cost a live deploy.

    The image's ENTRYPOINT ends `exec gunicorn … "$@"`, so a `command:` with no
    `entrypoint: []` becomes gunicorn's ARGUMENTS: `gunicorn: error:
    unrecognized arguments: celery -A config.celery worker`, the container
    restart-loops, and — worse — everything above that exec line still runs, so
    the worker executes `manage.py migrate` and the reference-data sweep ON
    EVERY RESTART against the database the web container is migrating.

    RED-PROVED by deleting `entrypoint: []` from the service:
        AssertionError: celery-billing does not clear its entrypoint …
    """
    services = _compose()["services"]
    for name, svc in services.items():
        if "billing" not in _queues_of(svc):
            continue
        assert svc.get("entrypoint") == [], (
            f"{name} does not clear its entrypoint, so its command becomes "
            "gunicorn's argv: the container restart-loops AND runs `migrate` on "
            "every restart against the same database the web container migrates "
            "(DEF-338). A worker must never migrate."
        )


def test_cr051_q7__the_billing_worker_healthcheck_uses_a_shell_and_hostname():
    """DEF-340, and it has TWO halves — the second one looks fixed and is not.

    `CMD` is the exec form and runs no shell, so `$HOSTNAME` is never expanded.
    And `CMD-SHELL` alone is not the fix either: this image is Debian, `/bin/sh`
    is **dash**, and dash does not set `HOSTNAME` — a shell would expand it to
    the empty string, leaving `celery@`, and the check would go on failing for a
    second reason while looking repaired. `$(hostname)` is the form that works.

    RED-PROVED both ways:
      * `["CMD", …]` → AssertionError: … healthcheck is not CMD-SHELL …
      * `$$HOSTNAME` → AssertionError: … uses $HOSTNAME, which dash does not set …
    """
    services = _compose()["services"]
    for name, svc in services.items():
        if "billing" not in _queues_of(svc):
            continue
        test = (svc.get("healthcheck") or {}).get("test")
        assert test, f"{name} has no healthcheck at all"
        assert test[0] == "CMD-SHELL", (
            f"{name}'s healthcheck is not CMD-SHELL — the exec form runs no "
            "shell, so nothing expands a command substitution (DEF-340)"
        )
        line = " ".join(test[1:])
        assert "$HOSTNAME" not in line.replace("$$", "$").replace("$(hostname)", ""), (
            f"{name}'s healthcheck uses $HOSTNAME, which dash does not set — it "
            "would expand to the empty string and ping a node called 'celery@' "
            "for ever (DEF-340). Use $(hostname)."
        )
        assert "hostname)" in line, (
            f"{name}'s healthcheck does not resolve the node name with "
            "$(hostname); it can only be pinging a node that does not exist"
        )


# ── 3 · THE TWO NUMBERS, and the one that must never move ──────────────────
def test_cr051_q8__the_billing_worker_has_a_cpu_limit_and_a_replica_count():
    """The deliverable the PO actually asked for: *"eventually we should able to
    scale these works on the fly itf required"*. Not an autoscaler — two numbers
    an operator can change in this file, affecting billing and nothing else.

    RED-PROVED by deleting the `deploy:` block:
        AssertionError: celery-billing has no CPU limit — nothing bounds how
        much of the machine a bill run may take …
    which is precisely the state CR-051 task 28 measured: `deploy.resources`
    appeared NOWHERE in this file, and the clerk's accounts list went from
    605.8 ms to 2,868.9 ms at p95.
    """
    services = _compose()["services"]
    for name, svc in services.items():
        if "billing" not in _queues_of(svc):
            continue
        deploy = svc.get("deploy") or {}
        cpus = ((deploy.get("resources") or {}).get("limits") or {}).get("cpus")
        assert cpus, (
            f"{name} has no CPU limit — nothing bounds how much of the machine a "
            "bill run may take, which is the exact state CR-051 task 28 measured "
            "(accounts list p95 605.8 ms idle → 2,868.9 ms under two runs)"
        )
        assert float(cpus) > 0, f"{name}'s cpus limit {cpus!r} is not a positive number"
        assert deploy.get("replicas") is not None, (
            f"{name} has no replica count — the 'scale on the fly' half of the "
            "ruling is a number somebody can change, and there is no number"
        )


def test_cr051_q9__beat_stays_at_exactly_one_replica():
    """*"Beat is a clock, and two clocks do not conflict — they both fire."*

    It is asserted HERE, in the change that introduces a second scalable worker,
    because the decision log says exactly why: *"Whoever scales workers is the
    person who will scale this one too."* Two beats produce no error and no
    warning — partition archival runs twice over the same range, report
    retention DELETEs twice, the dispatcher paces at double rate.

    RED-PROVED by setting `celery-beat`'s replicas to 2:
        AssertionError: celery-beat runs 2 replicas — two clocks do not
        conflict, they both fire …
    """
    beat = _compose()["services"]["celery-beat"]
    replicas = (beat.get("deploy") or {}).get("replicas")
    assert replicas == 1, (
        f"celery-beat runs {replicas} replicas — two clocks do not conflict, "
        "they both fire, and nothing anywhere logs a warning about it"
    )


# ── 4 · the probe stopped being able to answer with a broadcast ────────────
def test_cr051_q10__would_run_asks_about_billings_own_queue():
    """A live `celery` worker answering a broadcast ping is no longer evidence
    that a BILL RUN will run — it consumes a different queue now.

    RED-PROVED by restoring `would_run()` to `core_jobs.dispatch_is_ready()`
    with no kind:
        AssertionError: would_run() asked the broadcast question (queue=None) …
    In that state a clerk is told the run is under way, the `billing` queue has
    no consumer, and the run rests `queued` for ever — DEF-320 rebuilt by the
    change that was meant to prevent a different harm.
    """
    asked: list[str | None] = []

    def _probe(queue=None):
        asked.append(queue)
        return True, "fake"

    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(_probe)
    try:
        run_jobs.would_run()
    finally:
        core_jobs.set_dispatch_probe(previous)

    assert asked == [run_jobs.BILLING_QUEUE], (
        f"would_run() asked about {asked!r}; it must ask about "
        f"{run_jobs.BILLING_QUEUE!r}. Asking the broadcast question (queue=None) "
        "lets a healthy exports worker answer for a queue nobody consumes"
    )


def test_cr051_q11__a_probe_written_before_the_split_is_still_asked_the_old_way():
    """Law 3 says defaults fail closed — but an ARITY is not a reason to refuse
    work a person is waiting for. A probe registered before CR-051 task 29 takes
    no argument; it must still be called, not treated as broken.

    RED-PROVED by calling `probe(queue)` unconditionally:
        AssertionError: assert (False, "probe raised TypeError") == (True, "old")
    """
    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(lambda: (True, "old"))
    try:
        assert core_jobs.dispatch_is_ready(run_jobs.CALCULATE_JOB) == (True, "old")
    finally:
        core_jobs.set_dispatch_probe(previous)


def test_cr051_q12__a_probe_that_raises_is_still_a_refusal():
    """The fallback above must not swallow a genuinely broken probe. A TypeError
    raised INSIDE a probe body would be indistinguishable from an arity mismatch
    if this were done with `except TypeError`, which is why it is done by reading
    the signature instead.

    RED-PROVED by implementing the fallback as `except TypeError: probe()`:
        the probe is called twice and the second call raises out of
        `dispatch_is_ready`, or worse, returns a stale True.
    """

    def _explodes(queue=None):
        raise TypeError("a genuine bug inside the probe")

    previous = core_jobs._dispatch_probe
    core_jobs.set_dispatch_probe(_explodes)
    try:
        ready, reason = core_jobs.dispatch_is_ready(run_jobs.CALCULATE_JOB)
    finally:
        core_jobs.set_dispatch_probe(previous)
    assert ready is False
    assert "TypeError" in reason


# ── 5 · the registry itself ─────────────────────────────────────────────────
def test_cr051_q13__all_three_bill_run_kinds_share_one_queue():
    """Splitting calculate from issue would put two halves of ONE bill run on two
    queues with two different CPU shares, and nothing would say so.

    RED-PROVED by registering only `CALCULATE_JOB`:
        AssertionError: billing.run.findings rides the default queue while
        billing.run.calculate rides 'billing' …
    """
    for kind in run_jobs.RUN_JOBS:
        assert core_jobs.job_queue(kind) == run_jobs.BILLING_QUEUE, (
            f"{kind} rides {core_jobs.job_queue(kind)!r} while the others ride "
            f"{run_jobs.BILLING_QUEUE!r} — one bill run, two CPU budgets"
        )


def test_cr051_q14__the_task_name_is_the_same_literal_in_both_files():
    """`config/celery_routes.py` pins the task name as a literal rather than
    importing `apps.tenancy.tasks` (a router that imports an app module is an
    import cycle). A pinned literal that drifts is a router that silently stops
    matching — and a router that stops matching is a CPU cap that silently stops
    applying, with every job still completing.

    RED-PROVED by changing either literal:
        AssertionError: assert 'smartbillhub.jobs.run_pending' == 'smartbillhub.jobs.run_pending_v2'
    """
    from apps.tenancy import tasks as tenancy_tasks

    assert celery_routes.RUN_PENDING_TASK == tenancy_tasks.RUN_PENDING_TASK


@pytest.mark.parametrize("kind", ["", None, "unknown.kind"])
def test_cr051_q15__an_unroutable_message_falls_through_to_the_default_queue(kind):
    """The failure mode is chosen, not accidental: a kind this router does not
    recognise lands on the DEFAULT queue, where the default worker runs it —
    slower and uncapped, which is exactly where this product was on 2026-08-30.
    Never lost, never stuck.
    """
    assert (
        celery_routes.route_job(
            celery_routes.RUN_PENDING_TASK, (), {"kind": kind} if kind is not None else {}
        )
        is None
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051 task 29 (PO ruling 2026-08-31) + BE-07 kernel core/jobs.py + the decision log's five constraints
# generated: 2026-08-31 by story-coder (CR-051 task 29 named-billing-worker lane)
# checklist: A✔ B=deferred(no-API-half — routing and a compose service add no endpoint) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half — a screen polls the job RECORD, so the queue that carried the message is invisible to it) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — every case above was proved RED on the real condition first, and the failure is quoted in its own docstring
# exceptions: this file reads `docker-compose.yml` from a pytest test, which is unusual and is deliberate — the CONSUMER half of a named queue lives in that file and nowhere else, and a Python-only test of routing would pass over a deployment with no consumer at all, which is the dangerous half · it cannot prove a real worker drains a real Redis queue; `10-scripts/verify_celery_transport.py` is the three-process proof
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
