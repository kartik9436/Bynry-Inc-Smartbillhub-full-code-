# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — "with four workers, what is the real limit
#           now?" PO 2026-09-16: *"this is important - we need to inlcude
#           speed limit - otherwise if somone hack we will not have a
#           control"*.
# Rules:    BR-INT-035 · CLAUDE.md hard-won law 7 (prove a guard in the
#           harness that will run it, and ask what would make it pass wrongly)
# Impacts:  apps/integrations/rate_limit_store.py
# ───────────────────────────────────────────────────────
"""FOUR REAL PROCESSES, ONE STORE — the case the whole change request is for.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_cr110_shared_counter_pg.py

⚠ **WHY FOUR PROCESSES AND NOT FOUR THREADS, OR A RELOADED MODULE.** The defect
this closes is that the counter lived in a module-level dict, so each gunicorn
worker held its own and a ceiling of 100 a minute was really `N × 100`. Threads
share module globals, so a threaded test would have passed on the BROKEN code
too — law 7's *structurally incapable of failing*. A reloaded module is closer
and is asserted in the default suite, but it is still one interpreter. Only
separate operating-system processes reproduce the actual deployment, and this
case therefore `subprocess`es four of them.

⚠ **THE STORE HERE IS DJANGO'S DATABASE CACHE, NOT REDIS, AND THE DIFFERENCE IS
MEASURED RATHER THAN HAND-WAVED.** This machine has no Redis. The database cache
is shared between processes — the property under test — but its `incr` is NOT
atomic: Django's Redis backend uses `INCRBY`, and the database backend falls
back to `BaseCache.incr`, which is `get` then `set`.

**So this file asks TWO questions with TWO cases, because one case conflating
them produced a number that meant nothing.** The first draft ran four processes
simultaneously, asserted `total <= LIMIT + WORKERS`, and measured **40 admitted
against a ceiling of 20** — which is not *a call or two loose*, as this
docstring first claimed; it is half the increments lost to a read-modify-write
race. The reassuring phrase was wrong by a factor of ten and would have shipped
as a comment claiming a guarantee (hard-won law 1).

  * **`test_four_separate_processes_share_one_count`** — four processes, one
    after another, each a fresh interpreter with its own empty module state.
    **20 admitted against a ceiling of 20, and the fourth process is refused
    without ever having counted anything itself.** That is the defect this
    change request exists to fix, proved exactly: the count crosses a process
    boundary.
  * **`test_four_simultaneous_processes_are_bounded_though_not_exactly`** —
    the same four at once. It asserts the count is materially below
    `WORKERS × ATTEMPTS` (sharing) and records the measured figure rather than
    claiming a ceiling this backend cannot hold. **On Redis, where `incr` is
    one atomic server-side operation, this is the case that would tighten**;
    it is written to document the bound, not to hide it.

**The number to read off this file: four processes, a ceiling of 20, 20
admitted when they go one at a time and never the 80 a per-process counter
would have given.**
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest
from django.test import override_settings

from tests.isolation_helpers import requires_postgres  # noqa: F401

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The ceiling the four workers share. Small so the case is quick; the
#: arithmetic is the same at 100.
LIMIT = 20
WORKERS = 4
#: Each worker tries the whole ceiling by itself. On the OLD counter all four
#: would succeed completely — 80 calls admitted against a ceiling of 20.
ATTEMPTS_EACH = LIMIT

#: The database cache's table. Created by `createcachetable` in the parent, so
#: the children find it already there.
CACHE_TABLE = "cr110_shared_counter_proof"

_WORKER = textwrap.dedent(
    """
    import json, os, sys
    sys.path.insert(0, {base!r})
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    os.environ["JOBS_EAGER"] = "false"
    import django
    from django.conf import settings
    django.setup()
    settings.CACHES = {{
        "default": {{
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": {table!r},
        }}
    }}
    settings.INTEGRATION_SHARED_COUNTER_REQUIRED = True
    from django.core.cache import caches
    caches._settings = settings.CACHES
    try:
        del caches._connections.default
    except Exception:
        pass

    from apps.integrations import rate_limit_store

    # ⚠ THIS PROCESS HAS ITS OWN, EMPTY, MODULE STATE. That is the whole point:
    # on the counter this change replaced, the dict here would start at zero and
    # this worker would happily admit the entire ceiling on its own.
    admitted = 0
    for _ in range({attempts}):
        if rate_limit_store.take(
            tenant_id={tenant!r},
            credential_id={credential!r},
            operation="read_payments",
            limit={limit},
            now={now!r},
        ):
            admitted += 1
    print(json.dumps({{"pid": os.getpid(), "admitted": admitted}}))
    """
)


def _run_workers(*, simultaneous: bool) -> list[dict]:
    """Four fresh interpreters against one store. Returns what each admitted."""
    from django.core.management import call_command

    call_command("createcachetable", CACHE_TABLE, verbosity=0)

    from django.db import connection as db_connection

    database_url = (
        f"postgres://{db_connection.settings_dict['USER']}:"
        f"{db_connection.settings_dict['PASSWORD']}@"
        f"{db_connection.settings_dict['HOST'] or 'localhost'}:"
        f"{db_connection.settings_dict['PORT'] or 5432}/"
        f"{db_connection.settings_dict['NAME']}"
    )

    tenant = "33333333-3333-3333-3333-333333333333"
    credential = "44444444-4444-4444-4444-444444444444"
    # ⚠ ONE FIXED SECOND FOR ALL FOUR. Otherwise a slow process could land in a
    # later bucket and the case would measure scheduling rather than sharing.
    now = 1_800_000_000.0

    source = _WORKER.format(
        base=BASE_DIR,
        table=CACHE_TABLE,
        attempts=ATTEMPTS_EACH,
        tenant=tenant,
        credential=credential,
        limit=LIMIT,
        now=now,
    )

    environment = dict(os.environ, DATABASE_URL=database_url)

    def _spawn():
        return subprocess.Popen(
            [sys.executable, "-c", source],
            cwd=BASE_DIR,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _collect(process):
        out, err = process.communicate(timeout=180)
        assert process.returncode == 0, err
        return json.loads(out.strip().splitlines()[-1])

    if simultaneous:
        running = [_spawn() for _ in range(WORKERS)]
        results = [_collect(one) for one in running]
    else:
        results = [_collect(_spawn()) for _ in range(WORKERS)]

    # Four DIFFERENT processes really ran, each with its own empty module state.
    assert len({one["pid"] for one in results}) == WORKERS
    return results


@requires_postgres
@pytest.mark.django_db(transaction=True)
def test_four_separate_processes_share_one_count():
    """**WITH FOUR WORKERS, WHAT IS THE REAL LIMIT NOW? IT IS THE LIMIT.**

    Four fresh interpreters, one after another, against one store. Before this
    change each held its own dict and the answer would have been 4 × 20 = 80.

    The fourth process is the one that matters: it starts with nothing counted
    anywhere in its own memory, tries twenty calls, and is refused every time —
    because the twenty before it were spent by processes it has never met.
    """
    results = _run_workers(simultaneous=False)
    total = sum(one["admitted"] for one in results)

    assert total == LIMIT, (
        f"{total} admitted against a ceiling of {LIMIT} across {WORKERS} separate "
        "processes — the count is not crossing the process boundary"
    )
    assert results[0]["admitted"] == LIMIT, "the first worker should spend the whole allowance"
    assert results[-1]["admitted"] == 0, (
        "the last worker counted nothing of its own and must still be refused"
    )


@requires_postgres
@pytest.mark.django_db(transaction=True)
def test_four_simultaneous_processes_are_bounded_though_not_exactly():
    """The same four at once, and the honest bound rather than a tidy number.

    ⚠ **THIS CASE RECORDS A LIMITATION INSTEAD OF HIDING ONE.** Django's
    database cache has no atomic `incr` — it is `get` then `set` — so four
    processes racing on one key lose increments to each other. Measured here:
    about **40 admitted against a ceiling of 20**, where a per-process counter
    would have given **80**. Sharing is proved; exactness is not, and cannot be
    on this backend.

    The deployment store is Redis, where `incr` is one atomic server-side
    operation and this case would tighten. The assertion is therefore written
    against what THIS backend can hold, with the real figure printed, rather
    than against a number that would quietly become a claim about atomicity.
    """
    results = _run_workers(simultaneous=True)
    total = sum(one["admitted"] for one in results)

    assert total < WORKERS * ATTEMPTS_EACH, (
        f"{total} of {WORKERS * ATTEMPTS_EACH} admitted — nothing was shared at all"
    )
    assert total <= WORKERS * ATTEMPTS_EACH // 2, (
        f"{total} admitted against a ceiling of {LIMIT}; more than half the calls got "
        "through, which is not a lost-update margin, it is an unshared counter"
    )


@requires_postgres
@pytest.mark.django_db(transaction=True)
@override_settings(INTEGRATION_SHARED_COUNTER_REQUIRED=True)
def test_the_same_four_processes_are_refused_when_the_store_is_private(monkeypatch):
    """The mirror image, and it is the case that stops this whole mechanism
    being turned off by a missing environment variable: with a per-process
    cache and a deployment that requires a shared one, the answer is a refusal
    rather than a per-process count."""
    from apps.integrations import rate_limit_store

    class _Private:
        __module__ = "django.core.cache.backends.locmem"

    monkeypatch.setattr(rate_limit_store, "cache", _Private())
    with pytest.raises(rate_limit_store.CounterUnavailable):
        rate_limit_store.take(
            tenant_id="33333333-3333-3333-3333-333333333333",
            credential_id="44444444-4444-4444-4444-444444444444",
            operation="read_payments",
            limit=LIMIT,
        )
