# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-027 (EP-INT-07) — "a nightly sweep that warns days ahead
#           with the date in words … once per day, never twice for the same
#           day", CR-069 wave H task H2
# Rules:    BR-TEN-081 (the utility's OWN clock decides what day it is) ·
#           BR-TEN-013 (cross-module work goes through the owner's published
#           callable, never its ORM) · B1 (a module reaches a neighbour by
#           name through its own seam file, never by importing it) ·
#           BR-INT-042 (the warning arrives days ahead, once a day)
# Tests:    06-backend/tests/test_us_int_027_expiry.py
# Impacts:  apps/integrations/expiry.py (the one caller) ·
#           apps/tenancy/selectors.py (`tenant_today`, the published read)
# ───────────────────────────────────────────────────────
"""integrations → tenancy: what day is it where this utility is?

WHY A WHOLE FILE FOR ONE DATE
------------------------------
`BR-INT-042` asks for a warning that arrives **once per day and never twice for
the same day**, and *day* is the word doing the work. A sweep that compared UTC
dates would warn a utility in `America/Chicago` twice on one of its own
afternoons and skip one of its own mornings, because a UTC boundary falls in the
middle of a Central working day. The rule is about the utility's calendar, so
the sweep has to ask whose calendar it is.

Tenancy owns that answer — `apps/tenancy/selectors.tenant_today` — and `B1`
says a module reaches a neighbour BY NAME through its own seam rather than by
importing it. This is that seam, and it is deliberately one read wide.

`None` IS NOT A DATE, AND IT IS NOT TODAY EITHER
------------------------------------------------
`today()` answers `None` when tenancy cannot answer at all — not installed, no
published callable, a read that raised. It never substitutes `date.today()`,
and the reason is `DEF-094` one module along: a fallback here would be a SECOND
copy of tenancy's fallback rule, and the two would part company the first time
either moved. The sweep treats `None` as *do not sweep* and says so in its
outcome, because a warning dated against the wrong calendar is worse than a
warning that has not arrived yet — it tells a utility its mailbox lapses on a
day that is not the day it lapses.

⚠ **THIS FILE READS. IT NEVER WRITES**, which is the same rule
`seams/notifications.py` states about itself and for the same reason: a seam
that can write is a cross-module write wearing a seam's clothes (`BR-TEN-013`).
"""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any

#: The neighbour's published read, named once so the contract is greppable from
#: BOTH sides of the boundary (G20 harvests these).
TENANCY_MODULE = "tenancy"
TODAY_READ = "tenant_today"
#: Wave K — the job record behind a run. `IntegrationRun.job_id` points at a row
#: in the `jobs` table, which tenancy owns, and S142 needs the two figures the
#: walk records on it: *asked them 4 times* and *window 61 of 105*.
#: ⚠ IT IS A SECOND READ AND NOT A SECOND SEAM. The alternative was for
#: `runs.py` to import `apps.tenancy.models.Job`, which is `BR-TEN-013`'s exact
#: prohibition — a cross-module read through somebody else's ORM.
JOB_READ = "job_poll"
#: `CR-110-BRC04` phase 2 — the partner door's third check. PO 2026-09-16:
#: *"you have to also check whether connector is activae whether tenant is
#: active"*. Tenancy owns what *active* means and publishes it, so the door
#: does not carry a second copy of a two-column predicate (`DEF-094`'s shape).
LIVE_READ = "tenant_is_live"


def _resolve(attribute: str, kind: str = "selectors") -> Any:
    """The owner's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{TENANCY_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def today() -> date | None:
    """Today on THIS utility's clock, or `None` when tenancy cannot say.

    `None` is not an error and not a date — it is the honest third answer, and
    the sweep is written to expect it. See the module docstring for why no
    fallback to `date.today()` lives here.
    """
    read = _resolve(TODAY_READ)
    if read is None:
        return None
    try:
        answer = read()
    except Exception:  # noqa: BLE001 — a read that fails must not crash a sweep
        return None
    return answer if isinstance(answer, date) else None


def job(job_id: Any) -> dict[str, Any] | None:
    """One job record of THIS tenant, or `None` (wave K, `US-INT-031` TC-3).

    Answers `None` for a job that is not this tenant's, for a malformed id and
    for a tenancy that has published no such read — the same honest third
    answer `today()` gives, and for the same reason. A run whose job has gone
    shows its counts and no progress, rather than an error.

    ⚠ **THE TENANT SCOPE IS THE NEIGHBOUR'S, NOT OURS.** `job_poll` filters on
    the session's tenant itself, so this seam cannot be handed an id from
    another utility and made to answer with it — which is the property that
    makes reading a run's progress safe from a list endpoint.
    """
    if job_id in (None, ""):
        return None
    read = _resolve(JOB_READ)
    if read is None:
        return None
    try:
        answer = read(job_id)
    except Exception:  # noqa: BLE001 — a read that fails must not break a screen
        return None
    return answer if isinstance(answer, dict) else None


def utility_is_live(tenant_id: Any) -> bool:
    """May this utility be served at all? — `CR-110-BRC04` phase 2, check 3.

    ⚠ **`None` IS NOT THE HONEST THIRD ANSWER HERE, AND THAT IS THE ONE PLACE
    THIS SEAM DIFFERS FROM ITS TWO NEIGHBOURS ABOVE.** `today()` and `job()`
    answer `None` when tenancy cannot say, and their callers treat that as *do
    not sweep* and *show no progress*. This read is a GUARD on a door an
    outside company presents a key at, so its third answer has to be **no**:
    a read that raised, a tenancy that published nothing, a malformed id — each
    of them is a reason to refuse and never a reason to serve (hard-won law 3,
    and the reason `rate_limit_store` has no `allow_on_error` either).

    ⚠ **IT RETURNS A BOOL AND NEVER RAISES**, because `resolve_caller` computes
    every guard on every path with no branch between them: an exception here
    would be an early exit from the one function in this module that must not
    have one, and the refusals would stop being one refusal.
    """
    read = _resolve(LIVE_READ)
    if read is None:
        return False
    try:
        answer = read(tenant_id)
    except Exception:  # noqa: BLE001 — a read that fails REFUSES; see the docstring
        return False
    return answer is True


__all__ = [
    "JOB_READ",
    "LIVE_READ",
    "TENANCY_MODULE",
    "TODAY_READ",
    "job",
    "today",
    "utility_is_live",
]


#: CR-173-BRC10 — the utility's own clock, as a zone. PO 2026-10-07 (Q2):
#: *"we need to use date and time setting from Tenant - we have that setting"*.
TIMEZONE_READ = "tenant_timezone"


#: `DEF-NOT-10571` — the utility's own language (Settings → Regional), which
#: an email rendered from a `default` template variant is written in.
REGIONAL_READ = "regional_settings"


def language() -> str | None:
    """The utility's language from `tenancy.selectors.regional_settings`, or
    `None` when tenancy cannot say. No fallback is invented on this side."""
    read = _resolve(REGIONAL_READ)
    if read is None:
        return None
    value = dict(read() or {}).get("language")
    return value if isinstance(value, str) and value.strip() else None


def timezone() -> Any:
    """The tenant's `ZoneInfo` (`tenancy.selectors.tenant_timezone`, BR-TEN-081).

    ⚠ **NO FALLBACK IS INVENTED HERE.** Tenancy's own read already answers UTC
    for a utility that has not chosen, and says why in its docstring; a second
    copy of that rule on this side of the seam is `DEF-094`'s shape. If tenancy
    publishes no such read the answer is `None`, and the caller refuses to name
    a day rather than guessing whose midnight it is.
    """
    read = _resolve(TIMEZONE_READ)
    if read is None:
        return None
    return read()


# ── `CR-198-BRC10` — which utility this is, and which utilities exist ─────────
SUBDOMAIN_READ = "subdomain_for_tenant"
TENANT_FOR_READ = "tenant_id_for_subdomain"
LIVE_UTILITIES_READ = "live_tenant_subdomains"


def subdomain() -> str | None:
    """THIS tenant's slug (the platform text sender and the callback path key
    on it), or None with no tenant in context — never somebody else's."""
    from core.tenancy import current_tenant_id

    tenant_id = current_tenant_id()
    read = _resolve(SUBDOMAIN_READ)
    if tenant_id is None or read is None:
        return None
    return read(tenant_id)


def tenant_for(utility: str | None) -> Any:
    """slug → tenant id, or None. Platform read on the RLS-exempt registry."""
    read = _resolve(TENANT_FOR_READ)
    if not utility or read is None:
        return None
    return read(str(utility))


def live_utilities() -> tuple[str, ...]:
    """Every live utility's slug — the reply door narrows a STOP to these."""
    read = _resolve(LIVE_UTILITIES_READ)
    return tuple(read()) if read is not None else ()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-027 (EP-INT-07 — the dated warning) · BR-INT-042 · BR-TEN-081
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B✔ C✔ D=n/a(no route of its own) E=n/a(no screen reads a seam) F✔ G✔ H=n/a(no secret crosses here)
# gates: pytest tests/test_us_int_027_expiry.py (the `None` path leaves the sweep declining rather than guessing) · G20 (the contract name is declared on both sides)
# exceptions: none — one read, no writer to reach for
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
