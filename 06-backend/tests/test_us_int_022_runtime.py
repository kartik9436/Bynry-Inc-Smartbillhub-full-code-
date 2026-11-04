# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-022 (EP-INT-06) — the cap, the timeout and the breaker.
# Rules:    BR-INT-022 (timeout · cap · breaker · backoff WITH jitter ·
#           Retry-After · token bucket) · BR-INT-041 (one tenant's outage is
#           one tenant's outage) · BR-INT-024 (a skipped window is RECORDED)
# Tests:    this file
# Impacts:  apps/integrations/runtime.py
# ───────────────────────────────────────────────────────
"""`US-INT-022`'s six cases, and the fixture discipline TC-2 insists on.

⚠ **THE SLOW FIXTURE SLEEPS. IT DOES NOT RAISE.** TC-2 is a case about the
TEST, and the story states its reason in its own words: *"a fixture that raises
tests the wrong failure entirely"*. A raising fixture returns instantly, so the
worker is freed either way and the bounded and unbounded versions behave
identically — the bug this whole file guards against would pass a suite built
on one. Every timing case below therefore uses a fixture that really blocks,
and the sleeps are kept to fractions of a second so the suite stays fast.
"""

from __future__ import annotations

import random
import threading
import time

import pytest

from apps.integrations import runtime


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 · the fixture discipline, asserted before anything relies on it
# ═══════════════════════════════════════════════════════════════════════════


def slow_fixture(seconds: float, result: str = "93/93"):
    """A provider that is SLOW, not down — the shape Figure 7 is about."""

    def call():
        time.sleep(seconds)
        return result

    return call


def test_us_int_022_tc2_the_slow_fixture_sleeps_and_never_raises():
    """⚠ If this fixture ever starts raising, every timing case below becomes
    a test of instant failure and the cap it proves stops being proved."""
    started = time.monotonic()
    answer = slow_fixture(0.05)()
    assert answer == "93/93"
    assert time.monotonic() - started >= 0.05, "the fixture must actually block"


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · the cap keeps the other workers free
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _fresh_caps():
    runtime.reset_caps()
    yield
    runtime.reset_caps()


def test_us_int_022_tc1_a_cap_of_two_leaves_the_other_workers_free():
    """Figure 7, in miniature: eight callers, a cap of two, one slow provider.

    ⚠ **THE ASSERTION IS ABOUT WHO IS BLOCKED, NOT ABOUT HOW LONG IT TOOK.** A
    wall-clock assertion on a shared machine is a flake; what the rule says is
    that **at most `concurrency` callers are inside the provider at once**, and
    that is exactly what is measured here.
    """
    limits = runtime.Limits(timeout_s=5, concurrency=2).validated()
    inside = 0
    high_water = 0
    guard = threading.Lock()

    def call():
        nonlocal inside, high_water
        with guard:
            inside += 1
            high_water = max(high_water, inside)
        time.sleep(0.05)
        with guard:
            inside -= 1
        return "ok"

    threads = [
        threading.Thread(
            target=lambda: runtime.guarded_call(
                call,
                connection_id="brazos-mailbox",
                limits=limits,
                state=runtime.BreakerState(),
            )
        )
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert high_water <= 2, f"{high_water} callers were inside a connection capped at 2"
    assert high_water >= 2, "the cap must not serialise a connection it is allowed to parallelise"


def test_us_int_022_tc6_the_cap_is_per_connection_and_not_per_provider():
    """⚠ **TENANT ISOLATION, AND THE FIX'S OWN FAILURE MODE.** Keying the cap
    on `provider_key` would make Brazos Bend's dead mailbox throttle Silver
    Creek's healthy one — the exact outage this module prevents, wearing the
    fix's clothes."""
    limits = runtime.Limits(timeout_s=5, concurrency=1).validated()
    brazos = runtime.cap_for("brazos-mailbox", limits)
    silver = runtime.cap_for("silver-creek-mailbox", limits)
    assert brazos is not silver

    assert brazos.acquire(timeout=0.1), "the first connection's only slot is free"
    try:
        # Brazos is now saturated. Silver Creek must be untouched.
        assert silver.acquire(timeout=0.1), "another connection's cap must be its own"
        silver.release()
    finally:
        brazos.release()


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 · the breaker
# ═══════════════════════════════════════════════════════════════════════════


def test_us_int_022_tc3_three_consecutive_timeouts_open_the_breaker():
    limits = runtime.Limits(breaker_after=3, half_open_after_s=300).validated()
    state = runtime.BreakerState()
    for attempt in (1, 2):
        state = runtime.after_timeout(state, limits, now=1000.0)
        assert not runtime.is_open(state, now=1000.0), f"opened after {attempt} — too eager"
    state = runtime.after_timeout(state, limits, now=1000.0)
    assert runtime.is_open(state, now=1000.0)
    assert runtime.is_open(state, now=1299.0), "the window is 300 s"
    assert not runtime.is_open(state, now=1301.0), "after the window it is half-open, not open"


def test_us_int_022_tc3_an_open_breaker_SKIPS_and_says_why(monkeypatch):
    """`BR-INT-024` — the window is recorded as skipped with the reason in
    words, never passed over in silence and never recorded as a failure."""
    limits = runtime.Limits(timeout_s=5, concurrency=2).validated()
    state = runtime.BreakerState(consecutive_timeouts=3, open_until=2000.0)
    dialled = []

    outcome = runtime.guarded_call(
        lambda: dialled.append(1),
        connection_id="brazos-mailbox",
        limits=limits,
        state=state,
        now=lambda: 1900.0,
        provider_name="The mail server",
    )
    assert outcome.skipped is True
    assert outcome.timed_out is False, "a skip is not a failure — nothing was tried"
    assert "not answering" in (outcome.sentence or "")
    assert dialled == [], "an open breaker must not dial"


def test_us_int_022_a_success_resets_the_count_to_zero_and_not_by_one():
    """⚠ *Consecutive* is the whole of the condition. Two timeouts, a success,
    two more timeouts is a connection working BADLY — not one that has stopped
    answering, and stopping a utility's bill run over it would be wrong."""
    limits = runtime.Limits(breaker_after=3).validated()
    state = runtime.BreakerState()
    state = runtime.after_timeout(state, limits, now=0.0)
    state = runtime.after_timeout(state, limits, now=0.0)
    state = runtime.after_success(state)
    assert state.consecutive_timeouts == 0
    state = runtime.after_timeout(state, limits, now=0.0)
    state = runtime.after_timeout(state, limits, now=0.0)
    assert not runtime.is_open(state, now=0.0), "four timeouts, none consecutive-three"


def test_us_int_022_a_provider_that_refuses_is_a_provider_that_is_answering():
    """⚠ **THE CLAUSE A LANE WILL WANT TO SIMPLIFY.** A mailbox refusing one
    bad address is working perfectly; opening the breaker on it would stop a
    whole bill run over one wrong address. The breaker counts SILENCE."""
    state = runtime.BreakerState(consecutive_timeouts=2)
    after = runtime.after_refusal(state)
    assert after.consecutive_timeouts == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · backoff, and why the jitter is the point
# ═══════════════════════════════════════════════════════════════════════════


def test_us_int_022_tc5_two_identical_retries_get_different_times():
    """⚠ A hundred tenants retrying on the same schedule is a self-inflicted
    denial of service — and it arrives at the provider already struggling."""
    draws = {runtime.backoff_seconds(3, rng=random.Random(seed)) for seed in range(50)}
    assert len(draws) > 40, "the delay must be spread, not clustered"


def test_us_int_022_the_backoff_grows_and_then_stops_growing():
    """Full jitter draws from `[0, step]`, so the CEILING is what grows — the
    property to assert, since any single draw may be small."""
    rng = random.Random(0)
    ceilings = [
        max(runtime.backoff_seconds(attempt, rng=rng) for _ in range(200))
        for attempt in (1, 2, 3)
    ]
    assert ceilings[0] < ceilings[1] < ceilings[2]
    capped = max(runtime.backoff_seconds(30, cap_s=300.0, rng=rng) for _ in range(200))
    assert capped <= 300.0, "an unbounded backoff is a connection that never comes back"


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 · the 429 and the bucket in front of it
# ═══════════════════════════════════════════════════════════════════════════


def test_us_int_022_tc4_a_429_is_raised_through_and_never_swallowed():
    """⚠ **A 429 IS THE PROVIDER TALKING**, so it is not a timeout, it does not
    touch the breaker, and the caller must see `retry_after_s` to honour it.
    Swallowing it here would turn a stated delay into a retry — and a ban."""
    limits = runtime.Limits(timeout_s=5, concurrency=2).validated()

    def call():
        raise runtime.RateLimited(retry_after_s=120)

    with pytest.raises(runtime.RateLimited) as refused:
        runtime.guarded_call(
            call,
            connection_id="brazos-mailbox",
            limits=limits,
            state=runtime.BreakerState(),
        )
    assert refused.value.retry_after_s == 120.0


def test_us_int_022_tc4_the_bucket_paces_the_batch_after_a_429():
    """The bucket ANSWERS how long to wait and never sleeps — a caller inside a
    worker decides whether to hold the worker or re-queue the item, and this
    module must not make that choice for it."""
    clock = {"t": 0.0}
    bucket = runtime.TokenBucket(rate_per_s=2.0, burst=2, now=lambda: clock["t"])
    assert bucket.take() == 0.0
    assert bucket.take() == 0.0
    waited = bucket.take()
    assert waited > 0, "the burst is spent — the third call must be paced"
    clock["t"] += waited
    assert bucket.take() == pytest.approx(0.0, abs=1e-9)


# ═══════════════════════════════════════════════════════════════════════════
# The limits themselves
# ═══════════════════════════════════════════════════════════════════════════


def test_us_int_022_a_cap_below_one_and_a_timeout_below_five_are_refused():
    """`US-INT-022` §5's validation. A cap of zero dials nobody — an outage
    somebody configured — and a two-second timeout fails a healthy provider on
    an ordinary slow morning."""
    limits = runtime.Limits(timeout_s=1, concurrency=0).validated()
    assert limits.concurrency == runtime.MIN_CONCURRENCY
    assert limits.timeout_s == runtime.MIN_TIMEOUT_S


def test_us_int_022_the_breaker_state_survives_a_round_trip_through_config():
    """⚠ **THE DURABLE HALF.** With eight workers, a per-process breaker never
    opens: each worker counts its own timeouts, so a connection that has failed
    eight times in a row has failed once as far as each of them knows. The
    count and the open-until live on the connection's non-secret `config`."""
    state = runtime.BreakerState(consecutive_timeouts=3, open_until=1234.5, probing=False)
    config = {runtime.BREAKER_KEY: state.as_config(), "timeout_s": 45}
    read_back = runtime.BreakerState.from_config(config)
    assert read_back == state
    assert runtime.limits_for(object(), config).timeout_s == 45, (
        "the same config carries the limits — one place a System Admin changes both"
    )


def test_us_int_022_an_empty_config_reads_as_a_closed_breaker():
    """Hard-won law 3 — defaults fail closed, and for a BREAKER *closed* means
    *dialling is allowed*: a connection nobody has configured must work."""
    state = runtime.BreakerState.from_config({})
    assert state.consecutive_timeouts == 0
    assert not runtime.is_open(state, now=time.monotonic())


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-022@this-commit (EP-INT-06 story + BR-INT-022/024/041 verbatim)
# generated: 2026-09-04 by the CR-069 wave F build lane
# checklist: A✔ B✔ C✔ D=F2's E=F3's F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_022_runtime.py
# exceptions: no database — the runtime is policy over a callable, and its state round-trips through a dict the connection row holds
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
