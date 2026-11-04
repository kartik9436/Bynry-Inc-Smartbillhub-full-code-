# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-002 (EP-CWP-01) — the throttle, and a lockout on the two
#           lookups worth guessing at. Screens: CWP-002 · CWP-012
# Rules:    BR-CWP-023 (quick pay and track lock for FIFTEEN MINUTES after FIVE
#           wrong attempts from the same address) · BR-CWP-025 (a second fact
#           only the sender would know) · BR-CWP-022 (this sits ON TOP of the
#           sixty-a-minute anonymous throttle, never instead of it) ·
#           CLAUDE.md hard rule 4 (financial immutability — and see below for
#           why that rule deliberately does NOT reach this state)
# Tests:    06-backend/tests/test_us_cwp_002_lockout.py
# Impacts:  apps/portal/guest_api.py (`track`, and quick pay in wave P)
# ───────────────────────────────────────────────────────
"""The lockout — five wrong pairs, fifteen minutes, per tenant · per form · per
address.

⚠ **IT IS NOT A TABLE, AND `US-CWP-002` §8 SAYS SO IN AS MANY WORDS:** *"The
lockout state is deliberately NOT a table. It is not a financial record and hard
rule 4 does not reach it; a lane that models it as one has added an append-only
row per wrong guess on a public endpoint."* Read that twice before "improving"
this file: an append-only table written by an anonymous stranger, once per wrong
guess, is a denial-of-service surface with an audit trail.

**THE KEY IS THREE THINGS AND EACH IS A TEST CASE.**

    portal:lock:<tenant id>:<form>:<address>

  * **tenant** — `TC-6`: locking `/pine-hill` leaves `/oak-ridge` open from the
    same address. A lockout is one utility's decision about one stranger.
    ⚠ **KEYED ON THE TENANT ID AND NOT ON THE SLUG.** A slug is a word a
    utility can change on Settings; changing it would silently unlock every
    door in the middle of an attack, and re-using a freed slug would inherit
    somebody else's lock. The id is what `require_tenant` has already resolved
    (`BR-CWP-005`) and it never moves.
  * **form** — `TC-5`: locking `track` does not lock quick pay. They are
    different doors and a person guessing references is not a person guessing
    bill numbers.
  * **address** — `TC-4`: the same six wrong pairs from a second address are not
    locked. The lock bounds ONE source, and the sixty-a-minute throttle above it
    bounds the rest.

**A CORRECT PAIR INSIDE THE WINDOW IS STILL REFUSED** (`TC-3`), and that is the
whole point of a lockout rather than a delay: guessing until you are right is
exactly the attack. **After the window a correct pair is accepted and the
counter is reset** (`TC-7`).

WHERE THE COUNTER LIVES, AND THE LIMITATION STATED
--------------------------------------------------
Django's default cache, the same place `guards.py` counts. On Redis (the
deployment shape) the count is shared by every worker and the lock is real. On
the per-process LocMem cache (tests, a bare `runserver`) each worker counts its
own, so a five-worker deployment without Redis would allow up to five times the
attempts before locking. That is a deployment fact and not a code path, and it
is written here rather than discovered later (hard-won law 1).
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from rest_framework.throttling import BaseThrottle

#: `BR-CWP-023`, both halves, as numbers a test can quote.
MAX_WRONG_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60

#: The two forms that take a reference. Quick pay's is wave P's; the constant is
#: here from the start so the two can never be spelt differently.
FORM_TRACK = "track"
FORM_QUICK_PAY = "quick_pay"

#: How long a run of wrong attempts is remembered before it fades. The same
#: fifteen minutes: six wrong guesses spread over an afternoon are somebody who
#: keeps mistyping their own reference, not somebody enumerating.
ATTEMPT_WINDOW_SECONDS = LOCK_SECONDS


def _attempt_key(tenant_key: str, form: str, address: str) -> str:
    return f"portal:lock:attempts:{tenant_key}:{form}:{address}"


def _lock_key(tenant_key: str, form: str, address: str) -> str:
    return f"portal:lock:until:{tenant_key}:{form}:{address}"


def address_of(request: Any) -> str:
    """The source address — DRF's anonymous throttle's OWN identity, so the lock
    and the throttle above it agree about who *"the same address"* is. A
    request with no address at all counts as one bucket rather than as none —
    an unknown source is not a free pass.

    ⚠ **IT CALLS DRF RATHER THAN RE-READING THE HEADER (`DEF-CWP-10710`, audit
    L3-02, 2026-10-30).** Until then this read `X-Forwarded-For`'s FIRST value —
    the end of the chain the VISITOR writes — while the docstring said it did
    what DRF does. DRF reads `xff[-NUM_PROXIES]`, the hop our own load balancer
    appended, and `NUM_PROXIES` is `TRUSTED_PROXY_COUNT` (`config/settings/
    base.py`, one setting for both). So anyone could send a fresh
    `X-Forwarded-For` with each guess, land in a fresh bucket every time, and
    never meet the five-try limit. With no trusted proxy configured the header
    is not read at all and the address is `REMOTE_ADDR`, exactly as for the
    throttle. **Do not re-implement the arithmetic here**: one identity, read
    one way, is the whole guarantee.
    """
    meta = getattr(request, "META", None)
    if meta is None:
        return "unknown"
    return BaseThrottle().get_ident(request) or "unknown"


def is_locked(tenant_key: str, form: str, address: str) -> bool:
    """Is this door shut for this source right now?"""
    return bool(cache.get(_lock_key(tenant_key, form, address)))


def record_wrong(
    tenant_key: str, form: str, address: str, *, max_attempts: int = MAX_WRONG_ATTEMPTS
) -> int:
    """One wrong pair. Returns how many wrong pairs are now on record; the
    `max_attempts`-th SHUTS the door for fifteen minutes.

    ⚠ **`max_attempts` IS A PARAMETER SINCE 2026-09-04 (CR-068 wave E) AND THE
    DEFAULT IS UNCHANGED.** `BR-CWP-023` gives quick pay and track five tries;
    `BR-CWP-036` gives the ENROLMENT form three, because it is a different door
    with a different prize — a reference lookup returns progress, and a wrong
    guess at enrolment is somebody trying to acquire a standing login on an
    account that is not theirs. Passing the number in beats a second
    module-level constant a caller could pick the wrong one of.

    `add` seeds the counter with its window exactly once and `incr` is atomic on
    every cache backend Django ships, which is the same shape `guards.py` uses
    for the in-flight budget.
    """
    key = _attempt_key(tenant_key, form, address)
    cache.add(key, 0, ATTEMPT_WINDOW_SECONDS)
    try:
        count = cache.incr(key)
    except ValueError:  # the key faded between add and incr — seed again
        cache.set(key, 1, ATTEMPT_WINDOW_SECONDS)
        count = 1
    if count >= max_attempts:
        cache.set(_lock_key(tenant_key, form, address), True, LOCK_SECONDS)
    return int(count)


def clear(tenant_key: str, form: str, address: str) -> None:
    """A correct pair OUTSIDE the window resets the counter (`TC-7`). Never
    called while the door is shut — inside the window a correct pair is refused
    and changes nothing, which is `TC-3`."""
    cache.delete(_attempt_key(tenant_key, form, address))
    cache.delete(_lock_key(tenant_key, form, address))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-002@d6d31c46 (EP-CWP-01 story + BR-CWP-022/023/025 verbatim)
# generated: 2026-09-04 by the CR-068 wave B build lane
# checklist: A✔ B✔ C✔ D✔(guest_api.py) E✔(the refusal sentence on CWP-012) F✔ G✔ H=n/a(no 🔒 path — no table, no money)
# gates: pytest tests/test_us_cwp_002_lockout.py · G81 (this file writes CACHE, never a row — `cache` is in the gate's NOT_A_ROW set)
# exceptions: on a LocMem cache the count is per process — stated, not hidden
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
