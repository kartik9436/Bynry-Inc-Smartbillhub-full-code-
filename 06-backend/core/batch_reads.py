# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B27
#           (changes row 55) — *"Each Check batch of 500 loads its accounts'
#           readings, plans and payments in one query set instead of per
#           account"*
# Findings: 04-docs/05-modules/07-billing/19-check-cost-measured.md
# Defects:  DEF-BIL-8491 (the read time every batch-loaded input is stamped
#           with) · DEF-BIL-8601 (the write-in-flight window it leaves)
# Rules:    CLAUDE.md hard rule 1 (the memo is keyed by, and refuses to answer
#           across, a tenant) · seam_batch.py's PO ruling (a memo that lives
#           inside ONE computation is allowed; a stored answer is forbidden)
# Tests:    06-backend/tests/test_b27_batch_reads.py
# ───────────────────────────────────────────────────────
"""ONE BATCH, ONE READ — what a bulk Check batch of 500 accounts shares.

The bulk Check (`billing.check_engine`) asked the database about 425 questions
per account, and about two thirds of them were IDENTICAL for every account —
the same tax row, the same rate tiers, the same charge-code amounts — while
almost all the rest were the same question about each account's own rows
(`19-check-cost-measured.md` §3). This module is the mechanism both halves use,
and it is deliberately small:

  * `batch()` opens ONE memo for ONE batch, on ONE thread, for ONE tenant, and
    destroys it in a `finally` when the batch ends;
  * `@memoised` on an OWNING module's read makes that read answer a repeated
    question from the memo while a batch is open — and behave exactly as it
    always did when none is (every caller outside the bulk Check);
  * `prime(fn, value, *args, **kwargs)` lets the owning module answer MANY
    accounts' questions from ONE query (an `IN (...)` over the batch) and put
    each answer where the per-account call will look for it.

WHY IN `core` AND NOT IN BILLING
--------------------------------
The reads it memoises belong to rating, metering, assets, customers and
tenancy, and those modules may not import billing (B1). `billing.seam_batch`
memoises at the SEAM, which billing owns; this memoises BELOW the seam, inside
the owning module's own selector, which only the owning module may decorate.
So the owner opts each read in by name, next to the read, where its reviewer
can check the key against what the answer depends on.

THE KEY IS EVERY ARGUMENT, BOUND TO ITS PARAMETER NAME
------------------------------------------------------
`f(x, on=d)` and `f(x, d)` are the same question and get the same key
(`inspect.signature(...).bind` + defaults); dropping an argument is how a memo
starts answering a different question, and BR-RAT-007's service date is the
argument that would do it on a money path (`seam_batch._key`'s warning, which
applies here unchanged). A list argument is keyed by its contents; an argument
nothing can key — a queryset, an object — sends the call straight through.

⚠ A MEMOISED READ MUST NOT ECHO AN ID ARGUMENT BACK: a UUID and its string
are keyed as one question, so `f(uuid)` may be answered with what `f(str)`
returned. Every read decorated today answers from the rows it reads.

THE TENANT IS PART OF EVERY KEY AND OF THE BATCH ITSELF (hard rule 1)
-------------------------------------------------------------------
A batch remembers the tenant it was opened for and ANSWERS NOTHING for any
other: `active()` returns None the moment the current tenant differs, so a read
made under another tenant's context goes to the database, where RLS FORCE
decides. B28 runs batches of different utilities in the same worker processes;
a memo that outlived its batch, or answered across tenants, would hand one
utility's tax rows to the next.

THE READ TIME (DEF-BIL-8491)
----------------------------
`Batch.read_at` is taken BEFORE the batch's first read. Every saved Check
result of the batch is stamped with it rather than with the moment it was
saved, so the staleness sweep's *"changed after checked_at"* covers everything
recorded after the batch read it — the payment posted while account 312 of 500
was being checked included. The residual window (a write whose transaction
began before the read time and committed after the read) is `DEF-BIL-8601`.

A MEMO, NOT A CACHE — THE PO RULING THIS STAYS INSIDE
-----------------------------------------------------
`billing.seam_batch` quotes it in full: a stored answer is forbidden; a memo
that lives inside ONE computation is not a stored answer. A batch is narrower
than a pass, so everything that module says about lifetime holds here with a
smaller number.
"""

from __future__ import annotations

import copy as _copy
import functools
import inspect
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from django.db.models import Model
from django.utils import timezone

from core import tenancy as core_tenancy

_UNKEYABLE = object()

#: ── READ CONTEXT THAT IS PART OF THE QUESTION (`CR-167-BRC10`, `BR-RAT-1066`) ─
#: A memoised read keyed only on its ARGUMENTS answers a second question with
#: the first one's answer when a context variable changes what the read means.
#: Rating's plan reads are the case: inside billing's gather they read the plan
#: version in force on the period end (`apps.rating.plan_versioning.
#: pricing_day`), so `plan_rate_schedules(plan)` asked for a December segment
#: and for a January segment are two questions. A module that owns such a
#: context registers a zero-argument callable here and its value joins every
#: key. Unset context contributes `None`, so a key is unchanged for every read
#: made outside one.
_CONTEXT_KEYS: list[Any] = []


def register_context_key(provider: Any) -> None:
    if provider not in _CONTEXT_KEYS:
        _CONTEXT_KEYS.append(provider)


def context_key() -> tuple[Any, ...]:
    """The registered context values, for a cache OUTSIDE this module that must
    key on them too (`apps.billing.seam_batch`)."""
    return tuple(provider() for provider in _CONTEXT_KEYS)


class Batch:
    """One batch's answers. Not thread-shared and not long-lived."""

    __slots__ = ("answers", "asked", "primed", "read_at", "served", "tenant_id")

    def __init__(self, tenant_id: Any, read_at: datetime) -> None:
        self.tenant_id = tenant_id
        #: The instant the batch's inputs were read — taken before the first
        #: read, so every saved result is stamped no later than the facts it used.
        self.read_at = read_at
        self.answers: dict[Any, Any] = {}
        #: Per-read counters, so a measurement can see what the memo bought.
        self.asked: dict[str, int] = {}
        self.served: dict[str, int] = {}
        self.primed: dict[str, int] = {}


_STATE = threading.local()


def _current() -> Batch | None:
    return getattr(_STATE, "batch", None)


def active() -> Batch | None:
    """The batch open on THIS thread for the CURRENT tenant, or None.

    A batch opened for tenant A answers nothing while tenant B is current —
    the read goes to the database and RLS decides (hard rule 1)."""
    found = _current()
    if found is None or found.tenant_id != core_tenancy.current_tenant_id():
        return None
    return found


@contextmanager
def batch(read_at: datetime | None = None) -> Iterator[Batch]:
    """One memo for one batch. Re-entrant: a nested call reuses the outer
    batch (one batch has one answer per question), and only the outermost
    `finally` discards it."""
    existing = _current()
    if existing is not None and existing.tenant_id == core_tenancy.current_tenant_id():
        yield existing
        return
    opened = Batch(core_tenancy.current_tenant_id(), read_at or timezone.now())
    previous = existing
    _STATE.batch = opened
    try:
        yield opened
    finally:
        # `finally`, so a batch that raises cannot leave a memo standing for the
        # next batch on this thread — which may be another tenant's.
        _STATE.batch = previous
        # The COUNTS only — never an answer — kept for a measurement to read.
        _STATE.last_counts = {
            "asked": dict(opened.asked),
            "served": dict(opened.served),
            "primed": dict(opened.primed),
        }


def last_counts() -> dict[str, dict[str, int]]:
    """How many times each read was asked, served and primed in the last batch
    this thread closed — counts only, no answers (a measurement's view)."""
    return dict(getattr(_STATE, "last_counts", None) or {})


def discard() -> None:
    """Drop whatever batch this thread holds. A belt-and-braces call for the
    end of a pass; `batch()`'s own `finally` is the real guarantee."""
    _STATE.batch = None


def _freeze(value: Any) -> Any:
    """A hashable stand-in for one argument. A UUID and its string are the SAME
    question (every memoised read filters on the id and none echoes the
    argument back), and a model row is its table and primary key."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Model):
        if value.pk is None:
            raise TypeError("an unsaved row has no identity to key on")
        return ("__row__", value._meta.label, str(value.pk))
    if isinstance(value, list):
        return ("__list__", tuple(_freeze(v) for v in value))
    if isinstance(value, tuple):
        return ("__tuple__", tuple(_freeze(v) for v in value))
    if isinstance(value, (set, frozenset)):
        return ("__set__", frozenset(_freeze(v) for v in value))
    if isinstance(value, dict):
        return ("__dict__", tuple(sorted((str(k), _freeze(v)) for k, v in value.items())))
    hash(value)
    return value


def _key(name: str, signature: inspect.Signature, args: tuple, kwargs: dict) -> Any:
    try:
        bound = signature.bind(*args, **kwargs)
    except TypeError:
        return _UNKEYABLE
    bound.apply_defaults()
    try:
        return (
            name,
            core_tenancy.current_tenant_id(),
            tuple((k, _freeze(v)) for k, v in bound.arguments.items()),
            tuple(provider() for provider in _CONTEXT_KEYS),
        )
    except TypeError:
        return _UNKEYABLE


def memoised(fn: Callable[..., Any] | None = None, *, copy: bool = False) -> Any:
    """Answer a repeated question from the open batch; outside one, `fn` itself.

    `copy=True` hands every caller its own deep copy — for a read that answers
    a list or dict a caller might change. A read answering a tuple of frozen
    facts needs none. An exception is never memoised: the next ask re-reads
    and raises again, exactly as without a batch.
    """

    def decorate(inner: Callable[..., Any]) -> Callable[..., Any]:
        name = f"{inner.__module__}.{inner.__qualname__}"
        signature = inspect.signature(inner)

        @functools.wraps(inner)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            found = active()
            if found is None:
                return inner(*args, **kwargs)
            key = _key(name, signature, args, kwargs)
            if key is _UNKEYABLE:
                return inner(*args, **kwargs)
            if key in found.answers:
                found.served[name] = found.served.get(name, 0) + 1
                value = found.answers[key]
            else:
                found.asked[name] = found.asked.get(name, 0) + 1
                value = inner(*args, **kwargs)
                found.answers[key] = value
            return _copy.deepcopy(value) if copy else value

        wrapper.batch_name = name  # type: ignore[attr-defined]
        wrapper.batch_signature = signature  # type: ignore[attr-defined]
        return wrapper

    if fn is not None:
        return decorate(fn)
    return decorate


def prime(fn: Callable[..., Any], value: Any, *args: Any, **kwargs: Any) -> bool:
    """Put `value` where `fn(*args, **kwargs)` will look for it in this batch.

    The OWNING module calls this after answering many accounts' questions in
    one query; it must answer exactly what `fn` would have (the batch-versus-
    per-account test holds every primer to that). Never overwrites an answer
    already in the memo. Answers False when no batch is open or the arguments
    cannot be keyed."""
    found = active()
    name = getattr(fn, "batch_name", None)
    if found is None or name is None:
        return False
    key = _key(name, fn.batch_signature, args, kwargs)  # type: ignore[attr-defined]
    if key is _UNKEYABLE:
        return False
    if key not in found.answers:
        found.answers[key] = value
        found.primed[name] = found.primed.get(name, 0) + 1
    return True


def put(namespace: str, key: Any, value: Any) -> bool:
    """Keep an owning module's batch-loaded rows under its own name, for a
    read whose question is not one exact key — a meter's heads over a WINDOW,
    from which any period inside it is answered. False when no batch is open."""
    found = active()
    if found is None:
        return False
    found.answers[("__store__", namespace, _freeze(key))] = value
    return True


def get(namespace: str, key: Any) -> Any:
    """What `put` kept under `namespace`/`key` in this batch, or None."""
    found = active()
    if found is None:
        return None
    try:
        return found.answers.get(("__store__", namespace, _freeze(key)))
    except TypeError:
        return None


def is_primed(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    found = active()
    name = getattr(fn, "batch_name", None)
    if found is None or name is None:
        return False
    key = _key(name, fn.batch_signature, args, kwargs)  # type: ignore[attr-defined]
    return key is not _UNKEYABLE and key in found.answers


__all__ = [
    "Batch",
    "active",
    "batch",
    "discard",
    "get",
    "is_primed",
    "last_counts",
    "memoised",
    "prime",
    "put",
]
