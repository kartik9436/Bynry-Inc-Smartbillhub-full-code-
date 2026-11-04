# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-022 (EP-INT-06) TC-1 · TC-2 · TC-3 · TC-6 — one utility's
#           dead mail server stays one utility's problem. Screens: S8 · S142
# Rules:    BR-INT-041 (P5 — one tenant's outage is one tenant's outage) ·
#           BR-INT-022 (hard timeout · cap · breaker) · BR-INT-024 (a skipped
#           window is RECORDED as skipped, never silent) · CLAUDE.md hard
#           rule 1 (every read and write under the tenant's context)
# Tests:    this file
# Impacts:  apps/integrations/runtime.py · services.py (`guarded_adapter_call`,
#           `record_skipped_run`) · runners/deliver.py · runners/fetch.py ·
#           jobs.py · seams/notifications.py
# ───────────────────────────────────────────────────────
"""The wave's exit test: Brazos Bend hangs, Silver Creek's 240 bills go out.

⚠ **WHY THIS FILE EXISTS BESIDE `test_us_int_022_runtime.py` AND DOES NOT
REPLACE IT.** That file asks *"how many callers were inside the provider at
once"* and answers 2, correctly. It says so in its own words — *"the assertion
is about who is blocked, not about how long it took"* — and on its own terms
that is right: a bare wall-clock assertion on a shared machine is a flake.

**But it is the wrong question for `BR-INT-041`, and the difference cost a
defect.** The rule is not about how many callers are inside the provider; it is
about **how many WORKERS one connection can consume**, and those were different
numbers. Two were inside the call and six more were blocked at the door of the
same connection for the full call timeout — thirty seconds each — so the
connection was holding all eight workers and the other tenant's run queued
behind it exactly as if there were no cap at all (`DEF-INT-4019`). Every
existing case passed over it, because every existing case counted the two.

**So the assertion here is the healthy tenant's own clock**, which is the only
thing that can tell a working guard from a broken one — and it is made
deterministic rather than generous:

  * the sick provider blocks on an `Event` that the test never sets until the
    end, so it is hanging for a KNOWN reason for the whole measurement rather
    than for a duration the machine might not respect;
  * the healthy tenant's call is asserted to have finished **while the sick one
    was still hanging** — an ordering, not a duration — with a wall-clock cap
    on top of it as a second, looser guard.

⚠ **AND THE FIXTURE BLOCKS, IT DOES NOT RAISE (`US-INT-022` TC-2).** The story
gives the reason in its own words: *"a fixture that raises tests the wrong
failure entirely"*. A raising fixture returns instantly, the worker is freed
either way, and a guarded and an unguarded runtime behave identically under it
— so a suite built on one proves nothing at all about the thing this wave is
for. `blocking_fixture` below is asserted to block before anything relies on it.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.integrations import models, runtime, services
from apps.integrations.adapters.base import ItemResult, RunResult
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import deliver
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar fixtures
from tests.test_us_met_helpers import tenant_ctx

SMTP = "email_smtp"

#: The pool the story names, and the cap it names (`US-INT-022` §4).
POOL = 8
CAP = 2
#: Short enough to keep the suite fast, long enough to be unambiguous. In
#: production this is `DEFAULT_QUEUE_WAIT_S` = 2 s against a 30 s call timeout.
QUEUE_WAIT_S = 0.2
#: The healthy tenant's budget. Deliberately many times the queue wait and many
#: times shorter than the call timeout: the defect this file was written for
#: made the healthy tenant wait `timeout_s`, so any budget between the two
#: separates a working guard from a broken one, and this one is not close.
HEALTHY_BUDGET_S = 5.0


@pytest.fixture(autouse=True)
def _fresh_caps():
    """The semaphores are process-local by nature, so a suite that changes a
    limit must clear them between cases."""
    runtime.reset_caps()
    yield
    runtime.reset_caps()


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 · the fixture discipline, asserted before anything rests on it
# ═══════════════════════════════════════════════════════════════════════════


class BlockingProvider:
    """A mail server that is SLOW, not down — the shape Figure 7 is about.

    It blocks until `release()` is called and then SUCCEEDS, which is the whole
    point: nothing raises, no error is ever handled, and a runtime with no
    guard in it looks completely healthy right up until every worker is asleep.
    """

    def __init__(self) -> None:
        self.gate = threading.Event()
        self.entered = threading.Semaphore(0)
        self._lock = threading.Lock()
        self.inside = 0
        self.high_water = 0
        self.calls = 0

    def __call__(self):
        with self._lock:
            self.calls += 1
            self.inside += 1
            self.high_water = max(self.high_water, self.inside)
        self.entered.release()
        self.gate.wait(timeout=30)  # a bound, so a broken test cannot hang the suite
        with self._lock:
            self.inside -= 1
        return "93/93"

    def release(self) -> None:
        self.gate.set()


def test_us_int_022_tc2_the_slow_fixture_blocks_and_never_raises():
    """⚠ If this ever starts raising, every case below becomes a test of
    instant failure and the guarantee it proves stops being proved."""
    provider = BlockingProvider()
    done = threading.Event()

    def run():
        provider()
        done.set()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert provider.entered.acquire(timeout=2), "the fixture never got started"
    assert not done.is_set(), "the fixture returned instead of blocking"
    provider.release()
    worker.join(timeout=5)
    assert done.is_set(), "the fixture blocked for ever instead of succeeding"


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · the whole wave: a slow tenant beside a healthy one, on one pool
# ═══════════════════════════════════════════════════════════════════════════


def test_us_int_022_tc1_a_hanging_connection_does_not_hold_another_tenants_workers():
    """Figure 7 in miniature, and the assertion is Silver Creek's stopwatch.

    Eight workers. Brazos Bend's mailbox hangs. Eight of Brazos Bend's batches
    are in flight — MORE than the cap on purpose, because the six that cannot
    get a slot are the ones the defect was hiding in. Silver Creek's batch is
    submitted afterwards, into the same pool, and must run **while Brazos Bend
    is still hanging**.
    """
    limits = runtime.Limits(
        timeout_s=30, concurrency=CAP, queue_wait_s=QUEUE_WAIT_S
    ).validated()
    provider = BlockingProvider()
    outcomes: list[runtime.Outcome] = []
    outcomes_lock = threading.Lock()

    def brazos_batch():
        outcome = runtime.guarded_call(
            provider,
            connection_id="brazos-mailbox",
            limits=limits,
            state=runtime.BreakerState(),
            provider_name="Custom SMTP",
        )
        with outcomes_lock:
            outcomes.append(outcome)
        return outcome

    def silver_creek_240_bills():
        return runtime.guarded_call(
            lambda: "240/240",
            connection_id="silver-creek-mailbox",
            limits=limits,
            state=runtime.BreakerState(),
            provider_name="Custom SMTP",
        )

    with ThreadPoolExecutor(max_workers=POOL) as pool:
        try:
            brazos = [pool.submit(brazos_batch) for _ in range(POOL)]
            # Wait until the cap is actually saturated, so the measurement
            # below starts from the state the story describes rather than from
            # a race.
            for _ in range(CAP):
                assert provider.entered.acquire(timeout=5), "the slow provider never got going"

            started = time.monotonic()
            silver = pool.submit(silver_creek_240_bills)
            answer = silver.result(timeout=HEALTHY_BUDGET_S)
            elapsed = time.monotonic() - started

            # ── the exit test, in three assertions ────────────────────────
            # 1 · the other tenant's work actually ran
            assert answer.value == "240/240"
            assert not answer.skipped, "Silver Creek's own connection was never busy"
            # 2 · and it ran WHILE Brazos Bend was still hanging. This is the
            #     ordering that makes the timing meaningful: without it, a pass
            #     could just mean the sick provider had already finished.
            assert not provider.gate.is_set()
            assert provider.inside == CAP, (
                f"{provider.inside} calls were still inside the hanging provider; "
                "the measurement did not happen during the outage"
            )
            # 3 · and it ran on the clock, not eventually. The defect made this
            #     `timeout_s` (30 s); the fix makes it `queue_wait_s`.
            assert elapsed < HEALTHY_BUDGET_S, (
                f"Silver Creek waited {elapsed:.1f}s behind another tenant's dead "
                f"mail server — BR-INT-041 says it should not have waited at all"
            )

            # ⚠ SNAPSHOT WHILE THE PROVIDER IS STILL HANGING, AND WAIT FOR THE
            # SIX FIRST. Two drafts of this block were wrong in opposite
            # directions and both are worth recording, because each was a
            # measurement error rather than a product failure:
            #
            #   * reading AFTER `release()` races this test's own cleanup — the
            #     moment the gate opens two slots free and a straggler still
            #     inside its queue wait takes one, so `calls` climbed to 4;
            #   * reading the instant Silver Creek returned found only ONE
            #     batch turned away, because Silver Creek needs exactly one
            #     free worker and runs the moment the first waiter gives up.
            #
            # Waiting for all six is deterministic and cannot hang: the two
            # inside are blocked on a gate this test holds shut, so no slot can
            # free and every remaining waiter MUST time out.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                with outcomes_lock:
                    if len(outcomes) >= POOL - CAP:
                        break
                time.sleep(0.01)
            placed = provider.calls
            high_water = provider.high_water
            with outcomes_lock:
                turned_away = [one for one in outcomes if one.skipped]
        finally:
            provider.release()
            for future in brazos:
                future.result(timeout=30)

    # ── and what the eight Brazos batches did, during the outage ──────────
    assert high_water == CAP, f"{high_water} callers were inside a connection capped at {CAP}"
    assert placed == CAP, (
        f"{placed} calls reached a mail server capped at {CAP} concurrent calls"
    )
    assert len(turned_away) == POOL - CAP, (
        f"{len(turned_away)} of {POOL} batches were turned away; expected {POOL - CAP} — "
        "the six that cannot get a slot must give the worker back, not queue for it"
    )
    assert {one.sentence for one in turned_away} == {"Too many calls at once."}
    # ⚠ **AND THIS IS THE ASSERTION THAT NAMES THE DEFECT DIRECTLY.** Each of
    # the six gave its worker back after the QUEUE WAIT (0.2 s here, 2 s in
    # production). Before `DEF-INT-4019` was fixed this number was the CALL
    # TIMEOUT — thirty seconds — and six workers sat at the door of a mail
    # server nobody was going to reach for every one of them.
    longest = max(one.waited_s for one in turned_away)
    assert longest < QUEUE_WAIT_S * 5, (
        f"a worker waited {longest:.1f}s for a slot on a connection that is not "
        f"answering; the queue wait is {QUEUE_WAIT_S}s"
    )


def test_us_int_022_the_queue_wait_can_never_be_raised_to_the_call_timeout():
    """`DEF-INT-4019`'s standing guard, in the place a config override lands.

    The bug was `queue_wait == timeout_s`. A System Admin editing the numbers
    on Settings has no way to know that setting them equal re-creates it, so
    `validated()` clamps rather than trusting.
    """
    limits = runtime.Limits(timeout_s=30, queue_wait_s=30).validated()
    assert limits.queue_wait_s <= limits.timeout_s / 2.0
    assert runtime.Limits().validated().queue_wait_s == runtime.DEFAULT_QUEUE_WAIT_S
    # and it is read off the connection's own non-secret config
    assert runtime.limits_for(None, {"queue_wait_s": 0.5}).queue_wait_s == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 · TC-6 · the same thing again with real rows, and two real tenants
# ═══════════════════════════════════════════════════════════════════════════


class _Operation:
    """The smallest thing `limits_for` and `start_run` need."""

    name = "send_bills"
    direction = "out"
    initiative = "us"
    timeout_s = 30
    concurrency = CAP


class HangingAdapter:
    """Its `execute` never answers inside the deadline."""

    def execute(self, view, secrets, work):  # noqa: ARG002 — protocol shape
        raise runtime.ProviderTimeout("the mail server did not answer")


class HealthyAdapter:
    def execute(self, view, secrets, work):  # noqa: ARG002 — protocol shape
        return RunResult(
            items=tuple(
                ItemResult(ref=str(one.get("ref")), outcome="succeeded") for one in work
            ),
            confirmed=True,
        )


def _connection(tenant, *, label):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=SMTP,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        cadence=models.CADENCE_MANUAL,
        config={},
    )


def _operation():
    """The real manifest operation where there is one, so the test is not
    asserting against a shape the product does not use."""
    manifest = REGISTRY.get(SMTP)
    for one in getattr(manifest, "operations", ()) or ():
        if (one.direction, one.initiative) == ("out", "us"):
            return one
    return _Operation()


@pytest.mark.django_db
def test_us_int_022_tc3_three_timeouts_open_the_breaker_and_the_next_run_is_recorded_skipped(
    brazos,
):
    """The breaker opens, the card says why in words, and the window that is
    not dialled leaves a ROW (`BR-INT-024`) — never silence."""
    operation = _operation()
    with tenant_ctx(brazos):
        connection = _connection(brazos, label="billing@brazosbend.example")
        work = [{"ref": "A-10432", "address": "a@example.test"}]

        for attempt in range(3):
            with pytest.raises(runtime.ProviderTimeout):
                deliver.execute_run(
                    connection=connection,
                    operation=operation,
                    adapter=HangingAdapter(),
                    work=work,
                    trigger="scheduled",
                )
            connection.refresh_from_db()
            state = runtime.BreakerState.from_config(connection.config)
            assert state.consecutive_timeouts == attempt + 1

        # ── the card ─────────────────────────────────────────────────────
        assert connection.status == models.STATUS_NOT_WORKING
        assert connection.last_test_ok is False
        assert connection.last_test_text is not None
        assert "not answering" in connection.last_test_text
        assert len(connection.last_test_text.split()) <= 6, "B14 rule 33 — six words"

        # ── the next due window: skipped, and RECORDED ───────────────────
        run = deliver.execute_run(
            connection=connection,
            operation=operation,
            adapter=HangingAdapter(),
            work=work,
            trigger="scheduled",
        )
        assert run.outcome == models.OUTCOME_SKIPPED, (
            f"a window nobody dialled was recorded as {run.outcome!r}; "
            "before OUTCOME_SKIPPED existed the arithmetic made this 'succeeded'"
        )
        assert run.attempted == 0, "US-INT-022 §5 — attempted 0"
        assert run.summary and "not answering" in run.summary
        # and the adapter was genuinely never asked
        assert run.succeeded == 0 and run.failed == 0


@pytest.mark.django_db
def test_us_int_022_tc6_one_tenants_open_breaker_leaves_the_other_tenant_untouched(
    brazos, lonestar
):
    """⚠ **THE FIX'S OWN FAILURE MODE, AND IT IS INVISIBLE ON ONE TENANT.**
    Both utilities run the same `email_smtp` manifest. A breaker or a cap keyed
    on the provider key would make Brazos Bend's dead mailbox stop Lone Star
    Ridge's healthy one — `BR-INT-041`'s exact outage wearing the fix's
    clothes, and every single-tenant test in this repository would still pass.
    """
    operation = _operation()
    work = [{"ref": "A-10432", "address": "a@example.test"}]

    with tenant_ctx(brazos):
        sick = _connection(brazos, label="billing@brazosbend.example")
        for _ in range(3):
            with pytest.raises(runtime.ProviderTimeout):
                deliver.execute_run(
                    connection=sick,
                    operation=operation,
                    adapter=HangingAdapter(),
                    work=work,
                    trigger="scheduled",
                )
        sick.refresh_from_db()
        assert runtime.is_open(
            runtime.BreakerState.from_config(sick.config), now=time.time()
        ), "the sick connection's breaker should be open"

    with tenant_ctx(lonestar):
        healthy = _connection(lonestar, label="billing@lonestarridge.example")
        run = deliver.execute_run(
            connection=healthy,
            operation=operation,
            adapter=HealthyAdapter(),
            work=work,
            trigger="scheduled",
        )
        # the other utility's bills went out, on the same provider key
        assert run.outcome == models.OUTCOME_SUCCEEDED
        assert run.attempted == 1 and run.succeeded == 1
        healthy.refresh_from_db()
        assert healthy.status == models.STATUS_WORKING
        assert runtime.BreakerState.from_config(healthy.config).consecutive_timeouts == 0
        assert healthy.config.get(runtime.BREAKER_KEY, {}).get("open_until") is None

    # ── the two connections are two rows, stamped for two tenants ────────
    #
    # ⚠ **AND THE ROW-LEVEL ISOLATION IS NOT ASSERTED HERE, DELIBERATELY.**
    # This suite runs on SQLite, which has no row-level security at all, so a
    # queryset under `tenant_ctx` returns BOTH utilities' rows and an
    # `assert count == 1` here fails on a working product — which is exactly
    # what the first draft of this case did. Hard rule 1's proof for these
    # tables is `tests/test_us_int_014_pg.py` (five tables, zero rows with no
    # tenant set, under the NON-superuser probe role) and
    # `test_us_int_022_isolation_pg.py` beside this file for the two rows
    # below. What IS provable here is the thing this case is about: the
    # breaker is per CONNECTION, so one utility's is open while the other's
    # has never been touched.
    sick.refresh_from_db()
    healthy.refresh_from_db()
    assert sick.tenant_id != healthy.tenant_id
    assert sick.provider_key == healthy.provider_key == SMTP
    assert sick.status == models.STATUS_NOT_WORKING
    assert healthy.status == models.STATUS_WORKING


@pytest.mark.django_db
def test_us_int_022_the_breakers_durable_half_survives_a_fresh_process(brazos):
    """`DEF-INT-4016` — `open_until` is read back by a DIFFERENT worker, so it
    must be written on a clock that means the same thing there.

    ⚠ **THIS CASE USES THE REAL DEFAULT CLOCK ON PURPOSE.** Every other breaker
    case injects `now` as a bare float, which is how the wrong clock survived:
    the default parameter was exercised by nothing. Here the value is written
    by the product and read back against wall-clock time, which is the only
    comparison a second process can make.
    """
    operation = _operation()
    with tenant_ctx(brazos):
        connection = _connection(brazos, label="billing@brazosbend.example")
        for _ in range(3):
            with pytest.raises(runtime.ProviderTimeout):
                deliver.execute_run(
                    connection=connection,
                    operation=operation,
                    adapter=HangingAdapter(),
                    work=[{"ref": "A-1", "address": "a@example.test"}],
                    trigger="scheduled",
                )
        connection.refresh_from_db()

    stored = connection.config[runtime.BREAKER_KEY]["open_until"]
    # A monotonic value is seconds since an arbitrary origin — on Linux, boot —
    # so it is a small number. A wall clock is seconds since 1970.
    assert stored > 1_600_000_000, (
        "open_until looks like a monotonic reading, which is meaningless in the "
        "process that reads it back (DEF-INT-4016)"
    )
    assert stored <= time.time() + runtime.DEFAULT_HALF_OPEN_AFTER_S + 5
    # and it is genuinely in the future, so a second worker declines to dial
    assert runtime.is_open(runtime.BreakerState.from_config(connection.config), now=time.time())


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-022@eea15784 (EP-INT-06 §3 TC-1..6 + BR-INT-022/024/041 verbatim)
# generated: 2026-09-05 by the CR-069 wave F build lane
# checklist: A✔ B✔ C✔ D✔(deliver.execute_run is the real runner) E=F3's(the card's sentence on screen) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_022_isolation.py · tests/test_us_int_022_runtime.py
# exceptions: TC-4 (429 Retry-After) and TC-5 (jitter) are asserted in test_us_int_022_runtime.py and are not repeated here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
