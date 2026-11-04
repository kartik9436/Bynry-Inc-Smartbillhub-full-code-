# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-022 (EP-INT-06) — a per-connection concurrency cap, hard
#           timeouts and a breaker, so one tenant's dead mail server stays one
#           tenant's problem. US-INT-028 (EP-INT-07, wave K) — token exchange
#           in memory: a ten-minute token across a two-hour walk, and NOT one
#           credential row for it. Screens: S8 (the card) · S142 (the run row)
# Rules:    BR-INT-047 (token exchange never writes the credential table;
#           window and page size are declared data) · BR-INT-025 (credential
#           versions are written only by rotation) ·
#           BR-INT-022 (hard timeout · cap · breaker · backoff WITH JITTER ·
#           `Retry-After` honoured · a token bucket in front of a 429; slow
#           degrades to a queue, never an outage) · BR-INT-041 (P5 — one
#           tenant's outage is one tenant's outage) · BR-INT-024 (a skipped
#           window is RECORDED as skipped, never silent) · CLAUDE.md hard rule
#           1 (every read and write runs under the request's tenant context)
# Tests:    06-backend/tests/test_us_int_022_runtime.py ·
#           06-backend/tests/test_us_int_028_token_walk.py
# Impacts:  apps/integrations/runners/* (every adapter call goes through
#           `guarded_call`; `runners/fetch.py` mints through `TokenCache`) ·
#           apps/integrations/services.py (the connection's status and its
#           sentence) · S142's skipped row
# ───────────────────────────────────────────────────────
"""THE GUARD IN FRONT OF EVERY PROVIDER CALL.

WHY THIS FILE EXISTS, AND WHY THE FAILURE IT PREVENTS IS INVISIBLE IN TESTING
-----------------------------------------------------------------------------
The design's Figure 7: **the failure that turns a ticket into an incident**. One
utility's mail server does not go DOWN — it goes SLOW, ninety seconds a call.
Every worker that dials it blocks for ninety seconds. With eight workers and no
cap, eight of them are asleep inside one tenant's outage and **every other
utility's bill run queues behind it**.

⚠ **IT IS INVISIBLE IN TESTING BECAUSE A TEST FIXTURE THAT FAILS RAISES.** A
raising fixture returns instantly, the worker is freed, and the bounded and
unbounded versions behave identically. `US-INT-022` TC-2 exists for exactly
this and says so in its own words: *"a fixture that raises tests the wrong
failure entirely"*. The fixture must SLEEP.

THE FIVE GUARDS, AND WHAT EACH ONE IS FOR
------------------------------------------
1. **A hard timeout on every call** (manifest default 30 s, per operation). A
   call with no deadline is a worker with no deadline.
2. **A concurrency cap per CONNECTION** (default 2). Not per provider and not
   per tenant: `BR-INT-041` is about one CONNECTION's outage, and two utilities
   using the same `email_smtp` manifest must not share a limit — TC-6.
3. **A breaker**: three consecutive timeouts open it; it half-opens with ONE
   probe after 300 s. While open, nothing is dialled, the card reads *Not
   working* with the reason in words, and **the due run is recorded as skipped**
   rather than passed over in silence (`BR-INT-024`).
4. **Exponential backoff WITH JITTER.** The jitter is not a refinement: a
   hundred tenants retrying on the same schedule is a self-inflicted denial of
   service, and the retry storm arrives at the provider that is already
   struggling. TC-5 asserts two identical fixtures get different next-attempt
   times.
5. **`Retry-After` honoured, and a token bucket in front of a 429.** Retrying
   through a 429 turns a delay into a ban — the provider stops being slow and
   starts being closed.

WHAT IS DELIBERATELY NOT DECIDED HERE
-------------------------------------
**This module does not choose the transport and does not know what an adapter
does.** It is handed a callable and returns its result or a typed refusal, so
an adapter stays the anti-corruption layer and this stays the policy. A
`requests` timeout hard-coded in an adapter would be the same rule in a second
place, and the second place is the one that goes stale.

⚠ **AND THE BREAKER'S STATE IS DURABLE, NOT PROCESS-LOCAL — WHICH IS A
DEPARTURE FROM `US-INT-022` §5 AND IS RECORDED RATHER THAN SLIPPED IN.** The
story maps breaker state to *"in-memory + `integration_connection.status`"*. In
memory alone it does not work: with eight workers each counts its OWN
consecutive timeouts, so a connection that has failed eight times in a row has
failed once as far as each worker knows and the breaker never opens — which is
precisely the outage this file exists to stop, surviving the fix. So the COUNT
and the OPEN-UNTIL live on the connection's non-secret `config`, where every
worker sees the same number, and the in-memory copy is a cache in front of it.
The decision log of 2026-09-04 carries the reasoning.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

#: Manifest defaults (`US-INT-022` §4). A manifest operation may lower a
#: timeout or raise a cap; `config` may override per connection.
DEFAULT_TIMEOUT_S = 30
DEFAULT_CONCURRENCY = 2
DEFAULT_BREAKER_AFTER = 3
DEFAULT_HALF_OPEN_AFTER_S = 300
#: ⚠ **HOW LONG A WORKER WILL QUEUE FOR A SLOT — AND IT IS NOT THE CALL
#: TIMEOUT (`DEF-INT-4019`, 2026-09-05).** These are two different numbers that
#: shared one name for a day. `timeout_s` is *how long we tolerate a provider
#: that is answering slowly*; this is *how long a worker should stand at the
#: door of a connection that is already busy*. Using the first for the second
#: is what broke the guarantee: with a cap of 2 on a pool of 8, two workers
#: went into the call and the other six blocked at the door **for thirty
#: seconds each**, so the connection was holding all eight and the other
#: tenant's run queued behind it anyway. The cap was enforced perfectly and the
#: pool was consumed regardless.
#:
#: Two seconds, because a HEALTHY connection frees a slot in milliseconds and a
#: worker that waits a moment does useful work instead of writing a skip row
#: nobody needed; a SICK one never frees one, and two seconds of eight workers
#: is a cost a utility does not notice. It is clamped below `timeout_s` in
#: `validated()` so a config override cannot quietly restore the bug.
DEFAULT_QUEUE_WAIT_S = 2.0

#: `US-INT-022` §5's validation: a cap below one dials nobody and a timeout
#: below five seconds fails a healthy provider on an ordinary slow morning.
MIN_CONCURRENCY = 1
MIN_TIMEOUT_S = 5

#: Where the durable half of the breaker lives on `integration_connection.config`.
#: A single key holding a small dict, so one `config` write moves both numbers
#: and two workers cannot half-update it.
BREAKER_KEY = "breaker"

#: The words the card shows while the breaker is open. ⚠ **A SENTENCE, NOT A
#: STATUS CODE** (B14 rule 33 caps a refusal at five or six words) — a clerk
#: reads this off the screen to somebody on the telephone.
BREAKER_SENTENCE = "The mail server is not answering."
#: The generic form, for a connection that is not a mailbox. The provider's own
#: name is filled in by the caller, which is the only thing that knows it.
BREAKER_SENTENCE_GENERIC = "{provider} is not answering."


class ProviderTimeout(Exception):
    """The call did not answer inside its deadline. ⚠ **NOT a provider error**
    — nothing came back to quote, which is why it has its own type: a timeout
    counts towards the breaker and a refusal does not."""


class BreakerOpen(Exception):
    """The connection is not being dialled. Carries the sentence the card shows
    and the moment the probe is due, so a caller records a SKIPPED run with a
    reason rather than a failure with none (`BR-INT-024`)."""

    def __init__(self, sentence: str, probe_due_at: float) -> None:
        super().__init__(sentence)
        self.sentence = sentence
        self.probe_due_at = probe_due_at


class RateLimited(Exception):
    """The provider said `429`. `retry_after_s` is THEIR number, honoured as
    given — ⚠ retrying through a 429 turns a delay into a ban."""

    def __init__(self, retry_after_s: float) -> None:
        super().__init__(f"rate limited for {retry_after_s}s")
        self.retry_after_s = float(retry_after_s)


@dataclass(frozen=True)
class Limits:
    """What one operation on one connection is allowed to do."""

    timeout_s: int = DEFAULT_TIMEOUT_S
    concurrency: int = DEFAULT_CONCURRENCY
    breaker_after: int = DEFAULT_BREAKER_AFTER
    half_open_after_s: int = DEFAULT_HALF_OPEN_AFTER_S
    queue_wait_s: float = DEFAULT_QUEUE_WAIT_S

    def validated(self) -> "Limits":
        """`US-INT-022` §5 — a cap of zero dials nobody, and a two-second
        timeout fails a healthy provider on an ordinary slow morning.

        ⚠ `queue_wait_s` is CLAMPED BELOW `timeout_s`, not merely defaulted
        below it. A connection whose config raised the queue wait to the call
        timeout would re-create `DEF-INT-4019` exactly, and the person editing
        that field on Settings has no way to know that.
        """
        timeout_s = max(MIN_TIMEOUT_S, int(self.timeout_s))
        return Limits(
            timeout_s=timeout_s,
            concurrency=max(MIN_CONCURRENCY, int(self.concurrency)),
            breaker_after=max(1, int(self.breaker_after)),
            half_open_after_s=max(1, int(self.half_open_after_s)),
            queue_wait_s=max(0.0, min(float(self.queue_wait_s), timeout_s / 2.0)),
        )


def limits_for(operation: Any, config: dict[str, Any] | None = None) -> Limits:
    """The manifest's defaults for this operation, overridden by `config`.

    ⚠ **`config` IS THE NON-SECRET HALF OF A CONNECTION AND NOTHING ELSE.** A
    credential never reaches this file: the limits are numbers a System Admin
    may see and change on Settings, and nothing here should ever be handed
    something it must not log.
    """
    settings = dict(config or {})
    return Limits(
        timeout_s=int(settings.get("timeout_s", getattr(operation, "timeout_s", DEFAULT_TIMEOUT_S) or DEFAULT_TIMEOUT_S)),
        concurrency=int(settings.get("concurrency", getattr(operation, "concurrency", DEFAULT_CONCURRENCY) or DEFAULT_CONCURRENCY)),
        breaker_after=int(settings.get("breaker_after", DEFAULT_BREAKER_AFTER)),
        half_open_after_s=int(settings.get("half_open_after_s", DEFAULT_HALF_OPEN_AFTER_S)),
        queue_wait_s=float(settings.get("queue_wait_s", DEFAULT_QUEUE_WAIT_S)),
    ).validated()


# ═══════════════════════════════════════════════════════════════════════════
# Backoff — the arithmetic, kept pure so it can be asserted without a clock
# ═══════════════════════════════════════════════════════════════════════════


def backoff_seconds(attempt: int, *, base_s: float = 1.0, cap_s: float = 300.0,
                    rng: random.Random | None = None) -> float:
    """`base × 2^(attempt-1)`, capped, then **jittered across the whole range**.

    ⚠ **FULL JITTER, NOT A SMALL WOBBLE, AND THE DIFFERENCE MATTERS.** A ±10%
    wobble on a shared schedule still delivers a hundred tenants inside one
    second; drawing uniformly from `[0, computed]` spreads them across the
    whole window. That is the difference between a retry and a retry STORM,
    and the storm arrives at the provider that is already struggling.

    `attempt` is 1-based. `rng` is injectable so `US-INT-022` TC-5 can assert
    that two identical fixtures at the same step get DIFFERENT times without
    asserting a specific one — the property is the spread, never the value.
    """
    step = min(cap_s, base_s * (2 ** max(0, int(attempt) - 1)))
    return (rng or random).uniform(0.0, step)


# ═══════════════════════════════════════════════════════════════════════════
# The token bucket — what stands in front of a 429
# ═══════════════════════════════════════════════════════════════════════════


class TokenBucket:
    """A per-connection pace. ⚠ **IT IS NOT A RETRY LIMIT — IT IS A SEND RATE.**

    After a provider has said `429` once, the batch behind it must be paced or
    the next call earns another one. `take()` answers how long to wait, never
    sleeps: a caller inside a worker decides whether to hold the worker or put
    the item back on the queue, and this file must not make that choice for it.
    """

    def __init__(self, rate_per_s: float, burst: int, *, now: Callable[[], float] = time.monotonic):
        self.rate_per_s = float(rate_per_s)
        self.burst = int(burst)
        self._now = now
        self._tokens = float(burst)
        self._checked_at = now()
        self._lock = threading.Lock()

    def take(self, tokens: float = 1.0) -> float:
        """Seconds to wait before this call may go. `0.0` means go now."""
        with self._lock:
            now = self._now()
            self._tokens = min(
                float(self.burst), self._tokens + (now - self._checked_at) * self.rate_per_s
            )
            self._checked_at = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            missing = tokens - self._tokens
            return missing / self.rate_per_s if self.rate_per_s > 0 else float("inf")


# ═══════════════════════════════════════════════════════════════════════════
# The breaker — durable, because a per-process one never opens
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class BreakerState:
    """What the connection row remembers between calls."""

    consecutive_timeouts: int = 0
    open_until: float | None = None
    #: Set while ONE probe is allowed through after `half_open_after_s`. A
    #: second worker arriving in the same window is refused — a half-open
    #: breaker that lets everybody through is not half-open, it is closed.
    probing: bool = False

    def as_config(self) -> dict[str, Any]:
        return {
            "consecutive_timeouts": self.consecutive_timeouts,
            "open_until": self.open_until,
            "probing": self.probing,
        }

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "BreakerState":
        row = dict((config or {}).get(BREAKER_KEY) or {})
        return cls(
            consecutive_timeouts=int(row.get("consecutive_timeouts") or 0),
            open_until=row.get("open_until"),
            probing=bool(row.get("probing")),
        )


def is_open(state: BreakerState, *, now: float) -> bool:
    """Open means *do not dial*. A breaker whose window has passed is NOT open
    — it is half-open, and exactly one caller gets through."""
    return state.open_until is not None and now < float(state.open_until)


def after_timeout(state: BreakerState, limits: Limits, *, now: float) -> BreakerState:
    """One more consecutive timeout, and the breaker opens on the third."""
    count = state.consecutive_timeouts + 1
    if count >= limits.breaker_after:
        return BreakerState(
            consecutive_timeouts=count,
            open_until=now + limits.half_open_after_s,
            probing=False,
        )
    return BreakerState(consecutive_timeouts=count, open_until=None, probing=False)


def after_success(state: BreakerState) -> BreakerState:
    """⚠ **A SUCCESS RESETS THE COUNT TO ZERO, NOT BY ONE.** *Consecutive* is
    the whole of `BR-INT-022`'s condition: a connection that times out twice,
    succeeds, then times out twice more is a connection that is working badly,
    not one that is not answering."""
    return BreakerState(consecutive_timeouts=0, open_until=None, probing=False)


def after_refusal(state: BreakerState) -> BreakerState:
    """A provider that ANSWERED — with an error — is answering.

    ⚠ **THIS IS THE CLAUSE A LANE WILL BE TEMPTED TO SIMPLIFY, AND IT IS THE
    WHOLE POINT OF THE BREAKER.** A mailbox refusing a message because an
    address is bad is working perfectly; opening the breaker on it would stop a
    utility's whole bill run over one wrong address. The breaker counts
    SILENCE, and only silence.
    """
    return BreakerState(consecutive_timeouts=0, open_until=state.open_until, probing=state.probing)


# ═══════════════════════════════════════════════════════════════════════════
# The cap — per CONNECTION, never per provider
# ═══════════════════════════════════════════════════════════════════════════

#: One semaphore per connection id, made on first use. ⚠ **KEYED ON THE
#: CONNECTION AND NOT ON THE PROVIDER KEY** — `BR-INT-041` is about one
#: connection's outage, and two utilities on the same `email_smtp` manifest
#: must not share a limit (`US-INT-022` TC-6). Keying it on `provider_key`
#: would make one tenant's dead mailbox throttle another's healthy one, which
#: is the exact failure this module exists to prevent, wearing the fix's
#: clothes.
_CAPS: dict[str, threading.BoundedSemaphore] = {}
_CAPS_LOCK = threading.Lock()


def cap_for(connection_id: Any, limits: Limits) -> threading.BoundedSemaphore:
    key = str(connection_id)
    with _CAPS_LOCK:
        existing = _CAPS.get(key)
        if existing is None:
            existing = threading.BoundedSemaphore(limits.concurrency)
            _CAPS[key] = existing
        return existing


def reset_caps() -> None:
    """Test seam. The semaphores are process-local by nature — a cap is about
    THIS worker's threads — so a suite that changes a limit must clear them."""
    with _CAPS_LOCK:
        _CAPS.clear()


# ═══════════════════════════════════════════════════════════════════════════
# The one entry point
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Outcome:
    """What a guarded call did, for the run row that records it."""

    value: Any = None
    timed_out: bool = False
    skipped: bool = False
    #: The sentence a card or a run row shows. Plain language, no rule id
    #: (B14 rule 32).
    sentence: str | None = None
    waited_s: float = 0.0
    breaker: BreakerState | None = None


def guarded_call(
    call: Callable[[], Any],
    *,
    connection_id: Any,
    limits: Limits,
    state: BreakerState,
    now: Callable[[], float] = time.monotonic,
    provider_name: str = "the provider",
) -> Outcome:
    """Run `call` under the cap, the timeout and the breaker.

    ⚠ **THE TIMEOUT IS ENFORCED BY THE CALLER'S OWN TRANSPORT, AND THIS
    FUNCTION SAYS SO RATHER THAN PRETENDING OTHERWISE.** Python cannot
    interrupt a blocking socket read from the outside; a thread-based
    "timeout" abandons the worker and leaves the socket open, which is the
    resource leak dressed as a fix. So `limits.timeout_s` is handed to the
    adapter, the adapter gives it to its transport, and a transport that
    ignores it raises `ProviderTimeout` here when the wall clock passes the
    deadline — recorded honestly as *we stopped waiting*, which is what it is.

    Returns an `Outcome`; raises nothing except what `call` itself raises for
    an ordinary provider refusal, because a refusal is the caller's to record
    against the item rather than the connection.
    """
    started = now()
    if is_open(state, now=started):
        # `BR-INT-024` — the window is SKIPPED and recorded, never silent.
        return Outcome(
            skipped=True,
            sentence=BREAKER_SENTENCE_GENERIC.format(provider=provider_name),
            breaker=state,
            waited_s=0.0,
        )

    semaphore = cap_for(connection_id, limits)
    if not semaphore.acquire(timeout=limits.queue_wait_s):
        # Every slot on THIS connection is busy and the QUEUE WAIT passed —
        # `limits.queue_wait_s`, seconds, and never `limits.timeout_s`
        # (`DEF-INT-4019`). This is the line that makes `BR-INT-041` true: a
        # worker that cannot get in gives the pool back at once instead of
        # standing at the door of a connection that is not answering.
        #
        # ⚠ NOT COUNTED TOWARDS THE BREAKER, deliberately. This connection is
        # busy, which is not the same as not answering, and a busy connection
        # that opened its own breaker would punish a utility for having work.
        return Outcome(
            skipped=True,
            # B14 rule 33 — a status is at most SIX words. This read "Too many
            # calls to this connection at once" (eight) until 2026-09-05, when
            # it first became reachable from a screen.
            sentence="Too many calls at once.",
            breaker=state,
            waited_s=now() - started,
        )
    try:
        value = call()
    except ProviderTimeout:
        moved = after_timeout(state, limits, now=now())
        return Outcome(
            timed_out=True,
            sentence=BREAKER_SENTENCE_GENERIC.format(provider=provider_name),
            breaker=moved,
            waited_s=now() - started,
        )
    except RateLimited:
        # ⚠ A 429 is the provider TALKING. It is not a timeout, it does not
        # touch the breaker, and it must not be retried through — the caller
        # honours `retry_after_s` and paces the rest of the batch.
        raise
    except Exception:
        # An answer, even an unhappy one. See `after_refusal`.
        raise
    finally:
        semaphore.release()

    return Outcome(value=value, breaker=after_success(state), waited_s=now() - started)


# ═══════════════════════════════════════════════════════════════════════════
# The short-lived token — IN MEMORY, and the credential table never hears of it
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS IS THE HALF OF `US-INT-028` A NAIVE IMPLEMENTATION GETS WRONG, AND
# IT GETS IT WRONG BY DOING THE OBVIOUS THING.** The head-end issues a bearer
# token valid for TEN MINUTES. A collection of two years of history in seven-day
# windows is 105 windows and takes about TWO HOURS. So the token expires
# mid-walk, twelve times or more, and something has to mint a new one.
#
# The obvious something is `services.record_credential` — it already exists, it
# already versions, it already audits. **And it is the wrong answer, because
# `BR-INT-025` says versions are written only by ROTATION.** A mint is not a
# rotation: the long-lived pair we hold has not changed, nobody re-keyed
# anything, and no clerk did anything. Writing a version per mint would put
#
#     12 versions per walk × 12 walks a day ≈ **144 credential rows a day**
#
# on ONE connection, and the rotation history a clerk reads on S142 — the list
# whose whole job is to answer *when did this key last change* — would be
# unreadable inside a week. `US-INT-028` TC-1 asserts the count is **1 before
# and after**.
#
# ⚠ **THE EXIT TEST IS TRUE *PER CREDENTIAL*, NOT PER CONNECTION** (`CR-069`
# §20.8). Neptune is already bidirectional on ONE credential, which is exactly
# why nobody has hit `DEF-INT-4118`'s one-credential-per-connection limit here.
# If credentials become plural per connection, *"one credential row before and
# after"* must be read as *one row for the credential this walk used* — the
# claim is about the STORED PAIR, never about the connection.
#
# ⚠ **AND THE CACHE IS PROCESS-LOCAL, WHICH IS RIGHT HERE AND WAS WRONG FOR THE
# BREAKER TWELVE LINES UP.** The breaker had to be durable because eight workers
# each counting their own timeouts never reach three. A token is the opposite: it
# is a secret with a ten-minute life, and a SECOND worker minting its own is
# harmless — two tokens, both valid, one wasted request. Making it durable would
# mean writing a live bearer token to a database, which is the one thing
# `BR-INT-003` exists to prevent. So the worst case here is a few extra mints and
# the worst case the other way is a leaked credential.


class TokenCache:
    """Short-lived tokens, held in memory for the length of a walk.

    ⚠ **KEYED ON THE CREDENTIAL, NOT ON THE CONNECTION** (`US-INT-028` TC-6).
    Two utilities collecting from the same head-end vendor hold two different
    long-lived pairs, so they must get two caches and neither may ever present
    the other's token. The caller passes a key it builds from the tenant and the
    credential; nothing in this file knows what a tenant is, which is what keeps
    the module pure and assertable without a database.

    `mints` is exposed because it is the number the story asserts — *the token
    is re-minted **≥ 11** times mid-walk* — and a test that could only count
    mints by patching a private name would keep passing on the day somebody
    renamed it.
    """

    def __init__(self, *, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        #: key → (token, the moment it stops being usable)
        self._held: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        #: How many times `token_for` actually called `mint`, per key.
        self.mints: dict[str, int] = {}

    def token_for(
        self,
        key: str,
        mint: Callable[[], str],
        *,
        ttl_seconds: int,
        refresh_before_s: int = 30,
    ) -> str:
        """The cached token, or a freshly minted one when it has aged out.

        ⚠ **`refresh_before_s` IS SUBTRACTED FROM THE LIFETIME AND NOT ADDED TO
        THE CLOCK, AND THE DIFFERENCE IS A LIVE FAILURE.** A token minted at
        09:50 with a 600-second life is trusted until **09:59:30**, not until
        10:00:00 — because a call that PASSES the check at 09:59:59 arrives at
        the provider a second later with a token that is already dead, and the
        walk fails at window 61 for a reason no log line explains. The registry
        refuses a skew at or above the lifetime, which would make every token
        stale on arrival and mint on every single call.

        `mint` is a CALLABLE the caller supplies, never a name this module
        imports. That is deliberate: a test that patched a module attribute
        would go on passing the day the attribute was renamed, and the path this
        covers is the one that carries a real utility's head-end credential.
        """
        usable_for = max(1.0, float(ttl_seconds) - float(refresh_before_s))
        with self._lock:
            held = self._held.get(key)
            now = self._now()
            if held is not None and now < held[1]:
                return held[0]
        # ⚠ MINTED OUTSIDE THE LOCK. Minting is a NETWORK CALL, and holding a
        # process-wide lock across one would serialise every tenant's walk
        # behind the slowest provider — `BR-INT-041`'s failure, rebuilt inside
        # the fix for a different one. Two workers racing here mint twice and
        # both tokens work; that is the cost, and it is the right one.
        token = mint()
        with self._lock:
            self._held[key] = (token, self._now() + usable_for)
            self.mints[key] = self.mints.get(key, 0) + 1
        return token

    def forget(self, key: str) -> None:
        """Drop one key — a walk that finished, or a credential that rotated."""
        with self._lock:
            self._held.pop(key, None)

    def clear(self) -> None:
        """Tests, and a worker shutting down. The mint COUNTS are cleared too."""
        with self._lock:
            self._held.clear()
            self.mints.clear()


#: The one cache a worker process shares. ⚠ **A MODULE-LEVEL DICT OF LIVE
#: BEARER TOKENS, AND THAT IS THE POINT: it is the only place they exist.** They
#: are never written to `integration_credential`, never to `audit_log`, never to
#: a run row's summary and never to a log line — `BR-INT-003`'s three exits, and
#: `US-INT-028` TC-5 captures logs during a whole walk and asserts that neither
#: the long-lived pair nor any short-lived token appears in one.
TOKENS = TokenCache()


def reset_tokens() -> None:
    """Test seam, and the mirror of `reset_caps` above."""
    TOKENS.clear()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-022@this-commit (EP-INT-06 story + BR-INT-022/024/041 verbatim)
# generated: 2026-09-04 by the CR-069 wave F build lane
# checklist: A✔ B✔ C✔ D=F2's(the runners call this) E=F3's(the card's sentence) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_022_runtime.py
# exceptions: the breaker's durable half departs from US-INT-022 §5's "in-memory" and the decision log of 2026-09-04 says why — a per-process breaker never opens under eight workers
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
