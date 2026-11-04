# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-040 (Send) · US-BIL-037 (Check)
# Checks:   04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md F4
#           (*"Two clerks open the same run: the second sees who is working on
#           it; two Sends cannot both issue"*)
# Defect:   DEF-BIL-8512 (nothing recorded or showed who had a run open)
# Tests:    06-backend/tests/test_us_bil_037_clerk_checks.py (F4)
# ───────────────────────────────────────────────────────
"""Who else has this bill run open — a presence note, nothing more.

A clerk's screen says *"I am on this run"* every `HEARTBEAT_SECONDS` while it
is open, and is told who ELSE said so recently. It is a courtesy to the second
clerk, never a lock: nothing here refuses anything, and the guarantee that two
Sends cannot both issue a bill is the per-bill row lock in `issue_invoice` and
the send-break filter in `release.record_send_breaks`, proved on PostgreSQL.

**IT LIVES IN THE CACHE, WITH A TIME-TO-LIVE, AND THAT IS THE WHOLE DESIGN.**
A person who closes the tab stops saying so and falls out after
`PRESENCE_TTL_SECONDS`; nothing has to notice them leave, and no row outlives
them. So there is no table, no migration and no wall clock in billing (G6): the
cache's own expiry is the clock. On a deployment the cache is Redis and shared
by every web process (`config/settings/base.py` CACHES); on a single `runserver`
it is that process's memory, which is the walk's case.

One key per (run, person) carries the name, and one index key per run lists
who has ever said so. Reading asks each listed key and keeps the ones still
alive. The index is bounded by the staff who opened the run (10–20 people at
the top of the ICP) and expires a day after the last write.
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy

#: How long a person stays listed after their screen last said so.
PRESENCE_TTL_SECONDS = 90
#: How often the screen says so (the client's interval — kept here to be one number).
HEARTBEAT_SECONDS = 30
INDEX_TTL_SECONDS = 24 * 3600


def _cache() -> Any:
    from django.core.cache import cache

    return cache


def _base(run: Any) -> str:
    return f"billing:run-presence:{core_tenancy.current_tenant_id()}:{run.pk}"


def _name(user: Any) -> str:
    for attribute in ("full_name", "email", "username"):
        value = getattr(user, attribute, None) if user is not None else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    getter = getattr(user, "get_full_name", None)
    if callable(getter):
        value = getter()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "—"


def _user_id(user: Any) -> str | None:
    value = getattr(user, "id", None) or getattr(user, "pk", None)
    return None if value is None else str(value)


def touch(run: Any, user: Any) -> list[dict[str, str]]:
    """Say *this person has the run open*, and answer who else does."""
    me = _user_id(user)
    cache = _cache()
    base = _base(run)
    if me is not None:
        cache.set(f"{base}:{me}", {"name": _name(user)}, PRESENCE_TTL_SECONDS)
        listed = set(cache.get(f"{base}:who") or ())
        if me not in listed:
            listed.add(me)
            cache.set(f"{base}:who", sorted(listed), INDEX_TTL_SECONDS)
    return others(run, user)


def others(run: Any, user: Any) -> list[dict[str, str]]:
    """Everyone else whose screen said so within `PRESENCE_TTL_SECONDS`."""
    me = _user_id(user)
    cache = _cache()
    base = _base(run)
    out: list[dict[str, str]] = []
    for person in cache.get(f"{base}:who") or ():
        if person == me:
            continue
        seen = cache.get(f"{base}:{person}")
        if isinstance(seen, dict):
            out.append({"name": str(seen.get("name") or "—")})
    return sorted(out, key=lambda row: row["name"])


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-037@4cb6ab0 (sha1[:7] of 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md + 04-docs/05-modules/07-billing/02-business-rules.md, concatenated in that order)
# generated: 2026-09-30 by the final bulk-run lane (DEF-BIL-8512)
# checklist: A✔ B✔ C✔ D✔(POST /billing/runs/{id}/presence — check_api.run_presence) E✔(the bulk run screen's "Also on this run" line) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ · pytest tests/test_us_bil_037_clerk_checks.py::test_us_bil_037_f4__the_second_clerk_is_told_who_else_has_the_run_open✔ (red first) · J73 F4 walked at 1440
# exceptions: presence lives in the cache with a 90 s time-to-live, never in a table — it is who has the page open now, not a record
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
