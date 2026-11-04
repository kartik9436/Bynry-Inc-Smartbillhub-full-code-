# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — the shared counter behind the partner call
#           limit. PO 2026-09-16: *"you can have shared counter - and keep
#           nthe check in code - thats it"*.
# Rules:    BR-INT-035 · CLAUDE.md hard-won law 3 (fail closed) · hard-won law
#           7 part 3 (*what would make this check PASS WRONGLY?* — every one
#           of those answers is a case below)
# Tests:    this file. The FOUR-PROCESS proof is
#           tests/test_cr110_shared_counter_pg.py, because it needs a store
#           two processes can both reach and SQLite's LocMem is not one.
# Impacts:  apps/integrations/rate_limit_store.py · runners/serve.py
# ───────────────────────────────────────────────────────
"""The counter that made `N × 100/min` into `100/min`, and what it does when it breaks.

⚠ **THE CASE THIS FILE EXISTS FOR IS `test_an_unreachable_store_refuses`.**
Hard-won law 7's third habit says to ask what would make a check PASS WRONGLY,
and for a shared counter the answer is specific and nasty: if an unreachable
store meant *the limit stops applying*, an attacker would turn the guard off by
knocking over Redis and then have no limit at all — a rate limiter with a
switch on the outside of the building.

⚠ **AND `test_a_per_process_store_refuses_when_a_shared_one_is_required`
IS THE SAME QUESTION ONE LAYER OUT.** A deployment with no `CACHE_URL` gets
Django's per-process `LocMemCache`, which counts perfectly and privately, so
every worker allows the full ceiling and NOTHING ANYWHERE LOOKS WRONG. That is
the exact defect this change request was raised to fix, and it would have
reappeared through the fix, silently, on the first host somebody forgot to
configure.
"""

from __future__ import annotations

import time

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.integrations import rate_limit_store

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "22222222-2222-2222-2222-222222222222"
CREDENTIAL = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OTHER_CREDENTIAL = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture(autouse=True)
def _clean_counter():
    """⚠ `rate_limit_store.reset()`, NOT `cache.clear()`. The default cache is
    shared with every other part of the product, and emptying it between cases
    leaks OUT of this file — `test_us_int_023_..._once_a_mailbox_is_connected`
    failed in a seven-file run and passed in every smaller one for exactly that
    reason. A suite has no business wiping a store it shares."""
    rate_limit_store.reset()
    yield
    rate_limit_store.reset()


def _take(**kwargs):
    base = {
        "tenant_id": TENANT,
        "credential_id": CREDENTIAL,
        "operation": "read_payments",
        "limit": 3,
    }
    base.update(kwargs)
    return rate_limit_store.take(**base)


# ══════════════════════════════════════════════════════════════════════════
# The limit is the limit
# ══════════════════════════════════════════════════════════════════════════


def test_the_fourth_call_of_a_limit_of_three_is_refused():
    assert [_take() for _ in range(3)] == [True, True, True]
    assert _take() is False


def test_the_window_slides_so_a_minute_boundary_cannot_be_straddled():
    """A fixed bucket lets a partner take 2× the limit in two seconds by
    spending it at 11:59:59 and again at 12:00:00. A sliding window does not,
    and this is the case that tells the two apart — it is the reason the
    original counter kept timestamps and the reason this one keeps sixty
    one-second keys rather than one per-minute key."""
    start = 1_800_000_059.0  # …:59 of some minute
    assert [_take(now=start) for _ in range(3)] == [True, True, True]
    # One second later we are in the NEXT minute. A fixed bucket would reset.
    assert _take(now=start + 1.0) is False
    # Sixty-one seconds after the first three, they have left the window.
    assert _take(now=start + 61.0) is True


def test_two_operations_on_one_key_are_counted_separately():
    """Blueprint p017 — the limit is per connection AND per operation. Without
    this, a partner permitted 600 meter readings a minute would get 600 refunds
    a minute for free."""
    assert [_take(operation="read_payments") for _ in range(3)] == [True] * 3
    assert _take(operation="read_payments") is False
    assert _take(operation="read_bills") is True


def test_one_utilitys_partner_cannot_spend_anothers_allowance():
    """`BR-INT-035`, and it cannot be seen from inside one tenant. Two tenants
    on the same manifest have two windows."""
    for _ in range(3):
        assert _take() is True
    assert _take() is False
    assert _take(tenant_id=OTHER_TENANT) is True


def test_two_keys_at_one_utility_are_counted_separately():
    for _ in range(3):
        assert _take() is True
    assert _take() is False
    assert _take(credential_id=OTHER_CREDENTIAL) is True


# ══════════════════════════════════════════════════════════════════════════
# The counter is NOT in this process's memory — the N-workers property
# ══════════════════════════════════════════════════════════════════════════


def test_the_count_survives_reloading_the_module_that_holds_it():
    """**WITH FOUR WORKERS, WHAT IS THE REAL LIMIT NOW?** It is the limit.

    The old counter was a module-level dict, so each of `GUNICORN_WORKERS`
    processes held its own and the effective ceiling was N × the number. This
    case is the in-process half of the proof: it takes the whole allowance,
    throws away and re-imports the module that does the counting — the closest
    a single process can get to *a second worker starting up* — and shows the
    next call is still refused, because the count was never in the module.

    The REAL proof is four operating-system processes, and it is in
    `tests/test_cr110_shared_counter_pg.py`; this case is here because it runs
    in the default suite and goes red the day somebody moves the window back
    into a module global.
    """
    import importlib

    for _ in range(3):
        assert _take() is True

    # ⚠ HAND THE CLEANUP LEDGER ACROSS THE RELOAD. `importlib.reload` rebuilds
    # the module's namespace, so `_WRITTEN_KEYS` comes back EMPTY and the three
    # keys above stop being cleanable — the autouse fixture then leaves them in
    # the shared cache and the NEXT case in this file starts with its allowance
    # already spent. That is what made
    # `test_a_per_process_store_is_allowed_only_when_somebody_typed_so` fail in
    # a full-file run and pass on its own, which is a leak between cases rather
    # than flakiness.
    written = set(rate_limit_store._WRITTEN_KEYS)
    reloaded = importlib.reload(rate_limit_store)
    reloaded._WRITTEN_KEYS.update(written)

    assert (
        reloaded.take(
            tenant_id=TENANT, credential_id=CREDENTIAL, operation="read_payments", limit=3
        )
        is False
    )


# ══════════════════════════════════════════════════════════════════════════
# It fails CLOSED — the two ways the store can be missing
# ══════════════════════════════════════════════════════════════════════════


class _BrokenCache:
    """A store that is there and will not answer — Redis down, a timeout, a
    connection reset. It raises the way a real backend raises: from inside the
    call, with an exception this module has never heard of."""

    __module__ = "django.core.cache.backends.redis"  # it LOOKS shared

    class Boom(RuntimeError):
        pass

    def get_many(self, keys):
        raise self.Boom("Error 111 connecting to redis:6379. Connection refused.")

    def add(self, *a, **kw):  # pragma: no cover — never reached
        raise self.Boom("unreachable")

    def incr(self, *a, **kw):  # pragma: no cover — never reached
        raise self.Boom("unreachable")


def test_an_unreachable_store_refuses(monkeypatch):
    """**THE CASE THIS FILE EXISTS FOR.** The answer is `CounterUnavailable`,
    which `serve.check_rate_limit` turns into the same `429` an over-limit
    caller gets. It is NOT `True`, and there is no setting that makes it
    `True`: a guard an attacker can switch off by breaking its counter is not
    a guard."""
    monkeypatch.setattr(rate_limit_store, "cache", _BrokenCache())
    with pytest.raises(rate_limit_store.CounterUnavailable):
        _take()


class _PrivateCache:
    """Django's default when no `CACHE_URL` is configured. It works perfectly
    and privately, which is precisely the problem."""

    __module__ = "django.core.cache.backends.locmem"


@override_settings(INTEGRATION_SHARED_COUNTER_REQUIRED=True)
def test_a_per_process_store_refuses_when_a_shared_one_is_required(monkeypatch):
    """A deployment that forgets `CACHE_URL` refuses partner traffic rather
    than metering it per process — hard-won law 3, the same shape as
    `sslmode=disable` and `ALLOWED_HOSTS=localhost` each blocking a live
    deploy. The message names the backend it found and what to do."""
    monkeypatch.setattr(rate_limit_store, "cache", _PrivateCache())
    with pytest.raises(rate_limit_store.CounterUnavailable) as raised:
        _take()
    assert "locmem" in str(raised.value)
    assert "CACHE_URL" in str(raised.value)


@override_settings(INTEGRATION_SHARED_COUNTER_REQUIRED=False)
def test_a_per_process_store_is_allowed_only_when_somebody_typed_so():
    """The suite itself runs this way (`config/settings/test.py` says so, with
    a sentence). The point of the case is that turning it off is an explicit
    act with a name, not the consequence of an absent environment variable."""
    assert rate_limit_store.shared_counter_available() is False
    assert _take() is True


def test_a_genuinely_shared_backend_is_recognised():
    """⚠ **THE CASE THAT WAS MISSING, AND ITS ABSENCE HID A GUARD THAT COULD
    NEVER SAY YES.**

    `shared_counter_available()` first read `type(cache).__module__`. That is
    `django.utils.connection`, because `django.core.cache.cache` is a
    `ConnectionProxy` — the SAME string for Redis, memcached, LocMem and Dummy
    alike. So the function returned False for every backend there is, and a
    correctly configured Redis deployment would have refused **every** partner
    request.

    Every case around it passed. `test_a_per_process_store_refuses…` asserts
    False and got False; `test_an_unrecognised_backend…` asserts False and got
    False; `test_a_per_process_store_is_allowed_only_when_somebody_typed_so`
    asserts False and got False, for the wrong reason. **A suite that only ever
    asks a predicate to say no cannot tell a working predicate from one that is
    incapable of saying yes** — hard-won law 7's second shape, in a file whose
    own docstring is about that law.

    What actually found it was the four-process proof standing up a REAL shared
    backend and dying with *"the default cache is django.utils.connection"*.
    This case makes the same statement in the default suite, so it cannot come
    back quietly.

    ⚠ **AND IT CONFIGURES A REAL BACKEND THROUGH `CACHES` RATHER THAN PATCHING
    THE MODULE GLOBAL, WHICH IS THE SECOND THING THIS CASE TAUGHT.** The first
    draft subclassed `RedisCache` inside the test — and a class defined in a
    test module carries THAT module's `__module__`, not its base's, so it still
    read False and the case failed for a third, different reason. A double that
    has to imitate the exact attribute under test is a double that can only
    confirm what you already believe. `override_settings(CACHES=…)` builds the
    real object through the real handler, which is what a deployment does.
    """
    from django.core.cache import DEFAULT_CACHE_ALIAS, caches

    for backend, location in (
        ("django.core.cache.backends.redis.RedisCache", "redis://127.0.0.1:6379/9"),
        ("django.core.cache.backends.db.DatabaseCache", "some_cache_table"),
    ):
        with override_settings(CACHES={"default": {"BACKEND": backend, "LOCATION": location}}):
            # The handler really did build this backend — no connection is made.
            assert type(caches[DEFAULT_CACHE_ALIAS]).__module__ in (
                rate_limit_store.SHARED_BACKEND_MODULES
            )
            assert rate_limit_store.shared_counter_available() is True, backend

    # And the per-process one, through the same door, says False.
    with override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    ):
        assert rate_limit_store.shared_counter_available() is False


def test_an_unrecognised_backend_is_not_shared_until_somebody_says_so(monkeypatch):
    """`SHARED_BACKEND_MODULES` is an ALLOW list. A deny list of
    `{locmem, dummy}` would treat a wrapper class, a third-party backend or a
    typo in `CACHES` as shared, and the mistake would be silent and in the
    permissive direction."""

    class _Unknown:
        __module__ = "acme.cache.turbo"

    monkeypatch.setattr(rate_limit_store, "cache", _Unknown())
    assert rate_limit_store.shared_counter_available() is False


def test_the_access_log_says_WHICH_refusal_it_was(monkeypatch):
    """The caller gets the same `429` either way — that is deliberate. The RUN
    ROW does not, because a manager reading *rate limit reached* while the real
    cause is an unreachable counter goes and looks at the ceiling instead of at
    the store, and that is the expensive kind of wrong conclusion."""
    from apps.integrations.runners import serve

    over_limit = serve.PartnerRateLimited()
    uncountable = serve.PartnerRateLimited(countable=False)

    # Same on the wire.
    assert str(over_limit) == str(uncountable) == serve.REFUSAL_SENTENCE
    assert over_limit.retry_after_s == uncountable.retry_after_s
    # Different in the record.
    assert over_limit.window_text != uncountable.window_text
    assert "count" in uncountable.window_text
    # B14 rule 33 — a fact on screen is six words or fewer.
    for one in (over_limit, uncountable):
        assert len(one.window_text.split()) <= 6, one.window_text


def test_the_clock_is_wall_clock_and_not_monotonic():
    """Two machines counting into one store under `time.monotonic()` keys would
    count into DIFFERENT buckets, because a monotonic clock has no shared
    origin — and the limit would silently become N × the limit again, through
    the fix. The keys are named for wall-clock seconds, which is the same
    integer everywhere NTP reaches."""
    keys = rate_limit_store._keys(
        tenant_id=TENANT, credential_id=CREDENTIAL, operation="read_payments", second=1_800_000_000
    )
    assert len(keys) == rate_limit_store.WINDOW_SECONDS
    assert keys[-1].endswith(":1800000000")
    # …and the module reads `time.time()`, not `time.monotonic()`.
    before = int(time.time())
    _take()
    stored = [one for one in cache._cache] if hasattr(cache, "_cache") else []
    assert any(str(before) in str(one) or str(before + 1) in str(one) for one in stored), stored
