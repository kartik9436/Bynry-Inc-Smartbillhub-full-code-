# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INF-7683 (2026-09-28) — nobody could sign in at
#           smartbillhub.bynry.com. Every `POST /api/<slug>/auth/session`
#           answered 500 over
#           `psycopg.errors.UndefinedColumn: column
#            security_policies.absolute_session_hours does not exist`,
#           while `GET /api/health` answered `200 {"status":"ok"}` throughout.
#           The web tasks were serving code from a build that needs
#           `identity/0006` against a database that had not been migrated,
#           because the release task that migrates is a HUMAN step and the
#           rollout ran without it.
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee — the entrypoint PREDICTED this outage in prose on the day
#           it was written, and shipped no check beside the prediction) ·
#           law 2's mirror (a live screen behind a dead control; here, a healthy
#           probe in front of a dead process) · law 3 (defaults fail closed —
#           the unsafe option is the one you type) · law 7 (what would make this
#           check pass wrongly).
# Decision: 12-governance/02-decision-log.md, 2026-09-28 — "the web task refuses
#           to serve on a schema it cannot serve, and /api/health stays shallow".
# Tests:    06-backend/tests/test_def_inf_7683_schema_guard.py
# Gate:     10-scripts/gates/g136_release_step_cannot_be_skipped.py
# Impacts:  06-backend/docker-entrypoint.sh — every web task, every start.
# ───────────────────────────────────────────────────────
"""Is the database this process is about to serve migrated to the code it is running?

WHY THIS FILE EXISTS, AS A MEASUREMENT AND NOT AS AN ARGUMENT
=============================================================
`migrate` left `docker-entrypoint.sh` on 2026-09-28 (`CR-144-BRC07` task H4)
for three good reasons that are **not** reversed here: two tasks migrating
concurrently with no advisory lock, a slow migration failing the health check
it is being waited on by, and a scale-out running DDL. Migrations belong in
`docker-release.sh`, run once, before the rollout.

**What moved with them, and nobody noticed, is a GUARANTEE.** While every web
task migrated on boot, a task could not physically serve a schema older than
its code — the invariant was held by an implementation detail, not by a check.
The day the detail moved, the guarantee went with it and nothing went red.

Measured on real PostgreSQL 16 on 2026-09-28, clone at tip, `identity` rolled
back to `0005`, the app booted through the real `docker-entrypoint.sh`:

    GET  /api/health                      → HTTP 200  {"status": "ok"}
    POST /api/brazosbend/auth/session     → HTTP 500  {"code":"SYS-INTERNAL"}

    django.db.utils.ProgrammingError: column
      security_policies.absolute_session_hours does not exist

**A task in that state is worse than a task that is not there.** The balancer
keeps it in rotation because the probe is honest about the only thing it
measures, every request fails, and nothing in any log names the deploy — the
symptom is a column name.

REFUSE, NOT WARN — AND THE OTHER SIDE, ARGUED
=============================================
`docker-entrypoint.sh` already states the criterion this repo decides by:
`ALLOWED_HOSTS` **warns** because production settings against localhost is a
legitimate configuration; the RLS check **refuses** because *"serving is
strictly worse than not serving"*.

**FOR REFUSING.** A refusing task never binds port 8000, so it fails its health
check and is replaced — and under a rolling deploy the PREVIOUS task
definition's tasks keep serving. So the refusal converts *"the new build is up
and 500s every sign-in silently"* into *"the deploy does not complete, the old
build keeps serving, and the reason is the first thing in the new task's log."*
That is the same trade the RLS check makes and it is the stronger one here,
because unlike RLS the damage is visible to every customer at once.

**AGAINST — AND IT IS A REAL RISK, NOT A FORMALITY.** Pending is not the same
as *needed*. A migration that adds a column no code reads yet is harmless, and
a strict refusal turns that harmless state into a hard failure. The dangerous
moment is NOT the deploy — it is an unrelated task replacement: a spot
interruption, an AZ event, a scale-out at 9am. A task that refuses to boot then
takes capacity off a site that was working perfectly, and the guard has
manufactured the outage it exists to prevent.

**Nothing can tell those two apart from here.** Django knows a migration is
unapplied; it cannot know whether the running code reads the column. So the
resolution is law 3's, not a cleverer test: **refuse by default, and let an
operator who knows the pending migration is forward-compatible TYPE the
override** — `SBH_ALLOW_PENDING_MIGRATIONS=1`, printed loudly on every boot so
it cannot be left behind silently. The unsafe option is the one you type.

THREE OUTCOMES, BECAUSE `migrate --check` CAN ONLY EXPRESS TWO
==============================================================
Measured the same day, same machine:

    schema at tip                        `manage.py migrate --check` → exit 0
    identity rolled back to 0005         `manage.py migrate --check` → exit 1
    DATABASE_URL port 5499 (refused)     `manage.py migrate --check` → exit 1
    DATABASE_URL names a missing db      `manage.py migrate --check` → exit 1

**Exit 1 means "pending" OR "I could not ask".** A boot check written as
`manage.py migrate --check || exit 1` would therefore refuse to start during a
thirty-second RDS failover, and ECS would crash-loop the whole service through
a blip it would otherwise have ridden out. That is why this module returns
`UNREACHABLE` as its own third state and why the entrypoint treats it
differently: **"we could not tell" is never rendered as "it is fine", and never
as "it is broken" either.** (`rls_guard.RlsRuntimeStatus` has the same third
state for the same reason — that conflation is DEF-2717's mechanism one layer
up.)

On `UNREACHABLE` this **warns and boots**, deliberately. A process that cannot
reach the database fails every request whatever its schema, so refusing buys
nothing and costs the recovery: gunicorn that is up reconnects when the
database comes back, and a task that refused is gone.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY — hard-won law 7's second habit
=======================================================================
Named here rather than discovered later:

1. **The database is unreachable at boot.** The guard returns `UNREACHABLE`,
   warns, and the task serves. It is the honest answer and it is a hole: a
   stale schema behind an unreachable database boots exactly like a healthy one
   once the database returns. The line printed says so in those words, and a
   `PENDING` verdict is the only thing this guard ever refuses on.
2. **Someone types the override and leaves it in the task definition.** The
   loud line on every boot is the whole mitigation; `G136` cannot see a task
   definition.
3. **`django_migrations` says applied and the column is not there** — a
   hand-edited row, a partially-applied migration, a restore from a dump taken
   mid-migration. This guard reads Django's own ledger, so it believes the
   ledger. It would answer `CURRENT` over exactly the outage it was written
   for. Nothing short of reflecting every model field against the catalogue
   would catch that, and that check would be slow, fragile and would drift; it
   is a declared blind spot rather than an unnoticed one.
4. **The process never runs it.** `docker-entrypoint.sh` is the only caller, so
   a container that clears `entrypoint:` (every `celery*` service in
   `docker-compose.yml`, by design — DEF-338) is not covered. `G136` fails if
   the entrypoint stops calling it; nothing can make a cleared entrypoint call
   anything.

WHAT IT DELIBERATELY DOES NOT DO
================================
**It does not migrate.** Not on a fallback, not on a flag, not "just this
once". The three faults H4 names are still true and a web task must never run
DDL. This module has no write path at all — it opens a cursor on Django's
migration ledger and reads.

**It does not make `/api/health` a readiness check.** `core/health.py` is
shallow on purpose and `tests/test_health.py::
test_health_answers_with_the_database_unreachable` pins it that way: a probe
that queries the database turns a slow database into no service at all. The
answer to *"the probe said healthy while every sign-in 500'd"* is not to make
the probe deeper — it is that **the process answering the probe must not exist
when the schema is wrong.** After this guard, a stale-schema task never binds
the port, so the probe has no chance to lie about it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

#: Type this to boot anyway when the pending migration is known to be
#: forward-compatible. Hard-won law 3 — the unsafe option is the one you type.
#: Read from the environment so a live incident can be unblocked without a
#: rebuild, and from settings so a settings module can hold the same posture;
#: whichever granted it is printed.
ALLOW_PENDING_ENV = "SBH_ALLOW_PENDING_MIGRATIONS"

#: Optional settings flag of the same shape as `RLS_ALLOW_BYPASSING_ROLE`.
#: It is read with `getattr(..., False)` and is declared in no settings module
#: today — absent means False, which is the fail-closed default.
ALLOW_PENDING_SETTING = "SCHEMA_ALLOW_PENDING_MIGRATIONS"

_TRUE = {"1", "true", "yes", "on"}


class SchemaStatus(str, Enum):
    """What we were able to establish about the schema under this process.

    THREE states, not two. `UNREACHABLE` exists so that "we could not ask" can
    never be rendered as "the schema is fine" — nor as "the schema is stale".
    `manage.py migrate --check` collapses both into exit 1 and that collapse is
    the reason this module exists in Python rather than as one shell line.
    """

    CURRENT = "CURRENT"
    PENDING = "PENDING"
    UNREACHABLE = "UNREACHABLE"


@dataclass(frozen=True)
class SchemaVerdict:
    """The answer, plus everything a human woken at 3am needs to act on it."""

    status: SchemaStatus
    #: Every unapplied migration, as "app.name", in the order Django would
    #: apply them. Empty unless status is PENDING.
    pending: tuple[str, ...] = ()
    #: Why the database could not be asked. Empty unless status is UNREACHABLE.
    detail: str = ""

    @property
    def is_stale(self) -> bool:
        return self.status is SchemaStatus.PENDING

    def one_line(self) -> str:
        """The single line every caller prints. Always says what it measured."""
        if self.status is SchemaStatus.CURRENT:
            return (
                "the database schema matches this build: 0 unapplied migrations."
            )
        if self.status is SchemaStatus.PENDING:
            count = len(self.pending)
            return (
                f"THE DATABASE SCHEMA IS OLDER THAN THIS BUILD: {count} unapplied "
                f"migration(s). This process would answer 500 to any request that "
                f"reads a column they add (DEF-INF-7683)."
            )
        return (
            f"SCHEMA STATE UNKNOWN: the database could not be asked — {self.detail}. "
            f"This is NOT a pass and NOT a failure; nothing was proved either way."
        )


def allow_pending_is_typed() -> tuple[bool, str]:
    """Has a human typed the override, and where?

    Returns `(granted, who)`. `who` is printed beside the warning so a later
    reader can find and remove it — a tolerated unsafe state that does not name
    its own source is the thing nobody ever gets round to cleaning up.
    """
    raw = os.environ.get(ALLOW_PENDING_ENV)
    if raw is not None and raw.strip().lower() in _TRUE:
        return True, f"the environment variable {ALLOW_PENDING_ENV}={raw!r}"

    try:
        from django.conf import settings

        if getattr(settings, ALLOW_PENDING_SETTING, False):
            return True, f"settings.{ALLOW_PENDING_SETTING}"
    except Exception:  # settings not configured — the env var is the answer
        pass

    return False, ""


def read_verdict(connection=None) -> SchemaVerdict:
    """Ask Django's own migration ledger, and never guess when it cannot answer.

    This is exactly the question `manage.py migrate --check` asks — the plan to
    bring every leaf node up to date — read through `MigrationExecutor` so that
    "pending" and "unreachable" come back as different answers instead of as
    one exit code.
    """
    from django.db import DEFAULT_DB_ALIAS, connections
    from django.db.migrations.executor import MigrationExecutor
    from django.db.utils import OperationalError

    conn = connection if connection is not None else connections[DEFAULT_DB_ALIAS]

    try:
        executor = MigrationExecutor(conn)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
    except OperationalError as exc:
        # Connection refused, authentication refused, database does not exist,
        # a timeout, a failover in progress. All of them mean the same thing
        # here: we could not ask. They must not read as either answer.
        return SchemaVerdict(
            status=SchemaStatus.UNREACHABLE, detail=_first_line(str(exc))
        )

    if not plan:
        return SchemaVerdict(status=SchemaStatus.CURRENT)

    return SchemaVerdict(
        status=SchemaStatus.PENDING,
        pending=tuple(f"{m.app_label}.{m.name}" for m, _backwards in plan),
    )


def _first_line(text: str) -> str:
    """psycopg's connection errors are several lines; a boot log wants one."""
    line = text.strip().splitlines()[0] if text.strip() else "no detail given"
    return line[:300]


def refusal_message(verdict: SchemaVerdict) -> str:
    """What the operator reads when the task refuses. It must name the FIX.

    DEF-622's block in `docker-release.sh` is the model: an error that names
    neither the database, the cause nor the command is an error the person
    reading it cannot act on, and at 3am that is the whole cost of the incident.
    """
    listed = "\n".join(f"      {name}" for name in verdict.pending)
    return (
        "REFUSING TO SERVE ON A SCHEMA THIS BUILD CANNOT SERVE (DEF-INF-7683).\n"
        "\n"
        f"  {verdict.one_line()}\n"
        "\n"
        "  Unapplied:\n"
        f"{listed}\n"
        "\n"
        "  WHY THIS REFUSES INSTEAD OF WARNING. A task that boots here answers\n"
        "  500 to every request that touches a new column while its health probe\n"
        "  answers 200, so the balancer keeps it in rotation and nothing in any\n"
        "  log names the deploy. Refusing fails the rollout instead, and the\n"
        "  previous task definition keeps serving customers meanwhile.\n"
        "\n"
        "  THE FIX — run the release task, which is the step that migrates:\n"
        "\n"
        "      make release\n"
        "        (or, on the host)  docker compose run --rm --no-deps --entrypoint /app/docker-release.sh backend\n"
        "        (or, on ECS)       aws ecs run-task --task-definition smartbillhub-release-<env>\n"
        "\n"
        "  To see what is pending before you run it:\n"
        "      python manage.py showmigrations --plan | grep '\\[ \\]'\n"
        "\n"
        "  IF — AND ONLY IF — YOU KNOW EVERY MIGRATION ABOVE IS FORWARD-COMPATIBLE\n"
        "  (it adds something this build does not read), you may boot anyway by\n"
        "  typing it, and it will say so loudly on every boot:\n"
        f"      {ALLOW_PENDING_ENV}=1\n"
        "\n"
        "  Do NOT make this container migrate. Two tasks migrating at once take no\n"
        "  advisory lock, a slow migration fails the health check it is being\n"
        "  waited on by, and a scale-out must not run DDL (CR-144-BRC07 H4).\n"
        "  See 09-infra/02-aws-runbook.md §H6."
    )


def enforce_at_startup(connection=None, *, stream=None) -> SchemaVerdict:
    """The boot-path entry point. Prints one line always; refuses when fatal.

    Called from `docker-entrypoint.sh`, in the place `migrate` used to occupy —
    which is where a reader looks for it, and which makes the diff read as what
    it is: the replacement for the guarantee that left with the migrate.

    ⚠ ONE CALLER, DELIBERATELY, AND NAMED SO IT IS NOT MISTAKEN FOR AN
    OVERSIGHT. `rls_guard.enforce_at_startup` is also called from
    `config/wsgi.py` so that a `command:` override is still covered. This one is
    not, for two reasons: every `celery*` service in `docker-compose.yml` clears
    the entrypoint ON PURPOSE (DEF-338 — a worker must never migrate) and would
    then take a per-worker database round trip it has no use for, and a worker
    on a stale schema fails a job rather than an entire customer-facing site.
    `G136` fails if `docker-entrypoint.sh` stops calling this.

    Raises `django.core.exceptions.ImproperlyConfigured` when migrations are
    pending and nobody has typed the override.
    """
    import sys

    from django.core.exceptions import ImproperlyConfigured

    out = stream if stream is not None else sys.stderr
    verdict = read_verdict(connection)

    if verdict.status is SchemaStatus.CURRENT:
        # Print on the happy path too. A boot log that says nothing when all is
        # well cannot later prove the check ran at all — which is how a guard
        # becomes a paragraph (hard-won law 1).
        print(f"schema-guard: {verdict.one_line()}", file=out)
        return verdict

    if verdict.status is SchemaStatus.UNREACHABLE:
        print(f"schema-guard: ⚠ {verdict.one_line()}", file=out)
        print(
            "schema-guard: ⚠ Booting anyway: a process that cannot reach the "
            "database fails every request whatever its schema, and one that "
            "refused would be gone when the database comes back.",
            file=out,
        )
        return verdict

    granted, who = allow_pending_is_typed()
    if granted:
        print(f"schema-guard: ⚠ {verdict.one_line()}", file=out)
        print(
            f"schema-guard: ⚠ TOLERATED because {who} says so. Every one of the "
            f"migrations below is being ASSUMED forward-compatible with this build:",
            file=out,
        )
        for name in verdict.pending:
            print(f"schema-guard: ⚠     {name}", file=out)
        print(
            "schema-guard: ⚠ Run the release task and remove the override — "
            "`make release`, or docker-release.sh on the host.",
            file=out,
        )
        return verdict

    raise ImproperlyConfigured(refusal_message(verdict))
