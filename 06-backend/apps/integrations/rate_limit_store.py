# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — "the call limit is a GUARD, not a setting".
#           PO 2026-09-16, verbatim: *"this is important - we need to inlcude
#           speed limit - otherwise if somone hack we will not have a control"*
#           and *"so wecant allow clark to reset it; you can have shared counter
#           - and keep nthe check in code - thats it - it will solve - keep the
#           limit in database so if we want to change it later it is easy to
#           do"*.
# Rules:    BR-INT-035 (one utility's partner is bounded on its own) ·
#           CLAUDE.md hard-won law 3 (defaults fail closed — the unsafe option
#           must be the one you type) · hard-won law 1 (a comment claiming a
#           guarantee is not the guarantee: the limitation that remains is
#           NAMED here and carries its arithmetic) · hard-won law 7 (ask what
#           would make this check PASS WRONGLY — the answer is written down
#           below, with the test that holds it)
# Tests:    06-backend/tests/test_cr110_rate_limit_store.py
#           06-backend/tests/test_cr110_shared_counter_pg.py (four REAL
#           processes against one shared store — the N-workers proof)
# Impacts:  apps/integrations/runners/serve.py (the one caller) ·
#           config/settings/base.py (INTEGRATION_SHARED_COUNTER_REQUIRED) ·
#           config/settings/test.py (turns it off, in writing)
# ───────────────────────────────────────────────────────
"""The SHARED counter behind the partner call limit — and what it does when it cannot count.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: this file decides whether a machine
that is not signed in is allowed to keep calling). HUMAN-REVIEW-PENDING; the
row is in 12-governance/09-human-review-ledger.md.

WHAT THIS REPLACES, AND THE NUMBER THAT CHANGES
------------------------------------------------
`runners/serve.py` counted in a module-level dict. Its own docstring said what
that cost, honestly, and it is quoted rather than summarised because the
summary is where this goes wrong (hard-won law 1 — here the comment was TRUE
and a paraphrase would have been the lie):

    "This counter is PROCESS-LOCAL … With N gunicorn workers the effective
    limit is N × 100/min. That is a real gap … the limit as built protects one
    utility's partner from another's, and it does not protect the process from
    a distributed caller. A shared counter needs a store this product does not
    have yet."

**This deployment runs gunicorn with `GUNICORN_WORKERS` sync workers, default
3.** So a ceiling written as 100 a minute has been **300 a minute** since the
day it was written, and a partner spreading its requests across the four
workers of a slightly bigger box would have had 400. With this file the answer
is **100, whatever the worker count is** — that is the whole of what the PO's
ruling buys, and `tests/test_cr110_shared_counter_pg.py` proves it by running
FOUR REAL PROCESSES, each with its own empty module state, against one store.

THE STORE, AND WHY IT IS NOT A NEW ONE
---------------------------------------
**Django's default cache** — `django.core.cache.cache` — which
`config/settings/base.py` points at Redis when `CACHE_URL` is set, on a
different database index from Celery's broker.

It is chosen because **this repository already owns this job**. `apps/portal/
guards.py` counts three rate limits and an in-flight budget in exactly this
store, for exactly this reason, and its docstring records the same
per-process-versus-shared distinction. Adding a second mechanism would have
been the failure hard-won law 11 records three times in one night: a careful
operator reaching for the obvious general-purpose tool instead of asking
whether this repo already owns the job.

**What was considered and not chosen, so the next lane does not re-open it:**

  * **A table in PostgreSQL.** Genuinely atomic (`UPDATE … RETURNING`), tenant
    scoped, no new infrastructure. Rejected because it puts a write on the
    money database for every single partner request, including the ones we are
    about to refuse — the cheapest thing a refused request can cost is nothing,
    and this would have made a flood of refusals MORE expensive for us than for
    the caller. That is a rate limiter that helps the attacker.
  * **A file on disk.** Shared between workers on one box and not between two,
    and not atomic. Half an answer that looks like a whole one.

THE WINDOW IS STILL A SLIDING ONE, AND IT IS STILL A SLIDING ONE ON PURPOSE
----------------------------------------------------------------------------
The PO's third instruction was *"keep nthe check in code - thats it"*, so the
shape does not change: a partner still cannot take 200 in two seconds by
straddling a minute boundary. What changes is where the timestamps live.

A list of timestamps cannot be shared safely — read-modify-write over a cache
is a race with no atomic operation under it. So the window is **sixty
one-second counters**: one key per second, each with its own short lifetime,
summed on the way in. Sixty keys is ONE round trip (`get_many` is `MGET`), and
the resolution is a second rather than a microsecond, which is finer than any
limit expressed in calls per minute can observe.

⚠ **THE CLOCK CHANGES FROM `monotonic` TO `time.time()` AND THAT IS NOT A
TIDY-UP.** `time.monotonic()` has no shared origin — its zero is whatever the
platform chose, per process on some platforms and per boot on Linux — so two
machines counting into one store under monotonic keys would count into
DIFFERENT buckets and the limit would silently become N × the limit again,
through the fix. Wall-clock seconds are the same integer everywhere NTP
reaches. The cost is that a clock stepped backwards re-uses a bucket that is
still alive; the effect is bounded by one window and it is stated here rather
than left to be discovered.

WHAT HAPPENS WHEN THE STORE IS UNAVAILABLE — IT REFUSES
--------------------------------------------------------
**This is the question hard-won law 7 asks — *what would make this check pass
wrongly?* — and for a shared counter it has one specific answer: if an
unreachable store meant "the limit stops applying", we would have built a
guard an attacker turns off by knocking over Redis.** So:

  * **the store raises** (Redis down, a timeout, a connection reset) → the call
    is **REFUSED**, with the same `429` and `Retry-After` an over-limit caller
    gets. We cannot count, so we do not serve.
  * **the store is PER-PROCESS** (`LocMemCache`, `DummyCache`) → refused as
    well, unless the deployment has said in writing that it accepts a
    per-process count. `INTEGRATION_SHARED_COUNTER_REQUIRED` is **True** in
    `base.py` and turned off, deliberately and with a sentence, only in
    `config/settings/test.py`. A production box with no `CACHE_URL` therefore
    refuses partner traffic and says why in its logs, exactly as
    `sslmode=disable` and `ALLOWED_HOSTS=localhost` each blocked a live deploy
    (hard-won law 3). ⚠ And hard-won law 4: **editing a settings template never
    reaches a host that already has a `.env`** — a deployment that is missing
    `CACHE_URL` today has to be given one by hand.

⚠ **ATOMICITY IS A SEPARATE PROPERTY FROM SHAREDNESS AND ONLY ONE OF THEM IS
UNIVERSAL.** `cache.incr` is a single server-side operation on **Redis**
(`INCRBY`) and on **memcached**; on Django's **database** cache it is
`get`-then-`set` and two processes incrementing the same second can lose one of
the two. The deployment store is Redis, where it is atomic. The database cache
appears in this file's allow list because it is what makes the four-process
proof runnable on a machine with no Redis — and the proof it carries is
*shared*, which is the property under test. Under either backend the sum and
the increment are two operations, so a burst arriving in the same millisecond
can slip a few calls past the ceiling; that is a margin of error on a ceiling,
not a multiplication of it, and it is the same bound `apps/portal/guards.py`
lives with.
"""

from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.core.cache import DEFAULT_CACHE_ALIAS, cache, caches

#: One key per second of the window.
WINDOW_SECONDS = 60

#: How long a second's counter lives. The window plus a margin, so a key can
#: never expire while the sum that reads it is still interested in it.
BUCKET_TTL_SECONDS = WINDOW_SECONDS + 10

#: The key prefix. `intg` rather than `integrations` because this is on the hot
#: path of every partner request and the key travels on every one of them.
KEY_PREFIX = "intg:rl"

#: Cache backend modules whose count is visible to another PROCESS.
#:
#: ⚠ **AN ALLOW LIST AND NOT A DENY LIST, WHICH IS HARD-WON LAW 3 IN ONE LINE.**
#: A deny list of {locmem, dummy} would treat an unrecognised backend — a
#: wrapper, a third-party class, a typo in `CACHES` — as shared, and the failure
#: would be silent and in the permissive direction. An unknown backend is NOT
#: shared until somebody says so.
#:
#: `filebased` is deliberately ABSENT. It is shared between the workers on one
#: box and between no two boxes, and its `incr` is not atomic — half an answer
#: that looks like a whole one.
SHARED_BACKEND_MODULES = (
    "django.core.cache.backends.redis",
    "django_redis.cache",
    "django.core.cache.backends.memcached",
    #: Present for the four-process proof on a machine with no Redis. See the
    #: atomicity paragraph in the module docstring.
    "django.core.cache.backends.db",
)


#: The proxy classes `django.core.cache.cache` can be. See `_backend_module`.
_PROXY_TYPES = (type(cache),)


class CounterUnavailable(Exception):
    """The store could not be counted in. Raised by `take()` and turned into a
    refusal by its caller — never swallowed, never defaulted to *allow*."""


def _backend_module() -> str:
    """The module of the real cache BACKEND, resolved through `caches`.

    ⚠ **`type(cache).__module__` IS `django.utils.connection` AND NOT THE
    BACKEND'S, AND THE FIRST DRAFT OF THIS FILE USED IT.** `django.core.cache.
    cache` is a `ConnectionProxy`, so that expression answers the same string
    for Redis, memcached, LocMem and Dummy alike — which made
    `shared_counter_available()` **structurally incapable of returning True**
    (hard-won law 7's second shape). Every request would then have been refused
    on a correctly configured Redis deployment, and two cases in
    `tests/test_cr110_rate_limit_store.py` passed over it because they assert
    the answer is False.

    It was caught by the four-process proof, which is the only test here that
    stands up a REAL shared backend: the child processes died with *"the
    default cache is django.utils.connection, whose count is private to one
    process"*. **A guard that cannot say yes is as broken as one that cannot
    say no**, and only a case that expects a yes can see it — which is why
    `test_a_genuinely_shared_backend_is_recognised` now exists.

    `monkeypatch.setattr(rate_limit_store, "cache", …)` is how the tests inject
    a double, so a patched `cache` must still win over the registry.
    """
    patched = globals().get("cache")
    if patched is not None and not isinstance(patched, _PROXY_TYPES):
        return type(patched).__module__
    return type(caches[DEFAULT_CACHE_ALIAS]).__module__


def shared_counter_available() -> bool:
    """Is the default cache one whose count another process can see?

    Read at CALL time and not at import time, so a test — and a deployment that
    reconfigures `CACHES` — gets the answer that is true now.
    """
    return _backend_module() in SHARED_BACKEND_MODULES


def shared_counter_required() -> bool:
    return bool(getattr(settings, "INTEGRATION_SHARED_COUNTER_REQUIRED", True))


def _keys(*, tenant_id: str, credential_id: str, operation: str, second: int) -> list[str]:
    """The sixty one-second keys the window is made of, newest last.

    The operation is IN THE KEY, which is the whole of what makes the limit per
    operation as well as per connection: two operations on one key count
    separately, so a partner permitted 600 meter readings a minute does not get
    600 refunds a minute for free.
    """
    stem = f"{KEY_PREFIX}:{tenant_id}:{credential_id}:{operation}:"
    return [stem + str(one) for one in range(second - WINDOW_SECONDS + 1, second + 1)]


def take(
    *,
    tenant_id: Any,
    credential_id: Any,
    operation: str,
    limit: int,
    now: float | None = None,
) -> bool:
    """Count one call against the window. True = serve it, False = over limit.

    Raises `CounterUnavailable` when the store cannot be counted in — which the
    caller turns into the SAME refusal an over-limit caller gets. There is no
    third answer and deliberately no `allow_on_error` argument: an argument
    that could switch this to *allow* is the argument an attacker is trying to
    reach.
    """
    if not shared_counter_available() and shared_counter_required():
        raise CounterUnavailable(
            f"the default cache is {_backend_module()}, whose count is private to one "
            "process; set CACHE_URL, or set INTEGRATION_SHARED_COUNTER_REQUIRED=False "
            "to accept a per-process count"
        )

    second = int(time.time() if now is None else now)
    keys = _keys(
        tenant_id=str(tenant_id),
        credential_id=str(credential_id),
        operation=operation,
        second=second,
    )
    try:
        counted = cache.get_many(keys)
        total = sum(int(one) for one in counted.values())
        if total >= limit:
            return False
        here = keys[-1]
        # `add` seeds this second's key with its lifetime exactly once; `incr`
        # is the atomic operation on Redis. The `ValueError` arm is the key
        # expiring between the two, which on a one-second bucket is a real
        # race and not a theoretical one.
        cache.add(here, 0, BUCKET_TTL_SECONDS)
        _WRITTEN_KEYS.add(here)  # for `reset()` only — never read while serving
        try:
            cache.incr(here)
        except ValueError:
            cache.set(here, 1, BUCKET_TTL_SECONDS)
    except CounterUnavailable:
        raise
    except Exception as exc:  # the store is unreachable, slow, or refusing
        # ⚠ **THE BROAD `except` IS THE POINT AND A LATER LANE MUST NOT NARROW
        # IT.** Every cache backend raises its own family — `redis.exceptions`,
        # `pylibmc.Error`, a socket timeout, a `django.db` error under the
        # database cache — and this file may not import any of them to name
        # them. Narrowing this to a known list would let an unknown one escape
        # to the view, where it is a 500 that this door must never return, and
        # the fix for THAT would be a `try/except` in the view that allows the
        # call. Fail closed, here, once.
        #
        # ⚠ **AND IT DOES NOT LOG, WHICH IS A RULE RATHER THAN AN OVERSIGHT.**
        # The first draft called `log.warning` here and `G94` refused it by
        # name: this module is on the credential path, and `BR-INT-003` keeps a
        # logger off that path entirely, because a logger is where a secret
        # eventually leaks. **The fact is not lost** — it goes somewhere
        # better. `serve.check_rate_limit` turns this into
        # `PartnerRateLimited(countable=False)`, and `partner_api` writes the
        # run row *call limit could not be counted*, which is a durable record
        # in the product a manager can read on S142 rather than a line in a
        # container log nobody is tailing.
        raise CounterUnavailable(str(exc)) from exc
    return True


#: Every key this PROCESS has written, for `reset()` to delete again.
#:
#: ⚠ **THIS IS NOT THE COUNTER AND MUST NEVER BECOME IT.** The whole point of
#: this file is that the count lives in a SHARED store and not in a module
#: global; this set is a test-cleanup ledger and nothing reads it on the
#: serving path. It grows only while a process is alive and is bounded by the
#: number of distinct one-second keys that process has touched.
_WRITTEN_KEYS: set[str] = set()


def reset() -> None:
    """Test seam — delete the keys THIS module wrote, and nothing else.

    ⚠ **IT USED TO CALL `cache.clear()`, AND THAT WAS A REAL BUG WITH A
    REASSURING COMMENT ON IT** (*"safe because nothing but a test calls
    this"*). `serve.reset_partner_limits()` is called by three cases in
    `test_us_int_041_partner_surface.py`, and on the DEFAULT cache that
    sentence means **wipe everything every other part of the product has
    cached**. It showed up as `test_us_int_023_..._once_a_mailbox_is_connected`
    failing in a seven-file run and passing in every smaller one — the shape of
    a leak between suites, which is the most expensive kind of red because it
    reads as flakiness and gets re-run rather than read.

    Deleting only what we wrote is also the honest scope: a test seam has no
    business emptying a store it shares.
    """
    if _WRITTEN_KEYS:
        try:
            cache.delete_many(sorted(_WRITTEN_KEYS))
        except Exception:  # a broken store has nothing to clean up
            pass
        _WRITTEN_KEYS.clear()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 wave D (the two migrations) + PO rulings 2026-09-16 + blueprint p017
# generated: 2026-09-16 by the CR-110-BRC04 wave D build lane
# checklist: A✔ B=n/a(no screen — the number is display only and another lane renders the cell) C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 — row in 09-human-review-ledger.md)
# gates: pytest tests/test_cr110_rate_limit_store.py · tests/test_cr110_shared_counter_pg.py (four real processes, one store) · tests/test_us_int_041_partner_surface.py (the door's own TC-4 still passes through this)
# exceptions: the sum and the increment are two operations, so a burst in one millisecond can slip a few past the ceiling — a margin on a ceiling, not a multiplication of it, and the same bound apps/portal/guards.py lives with
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
