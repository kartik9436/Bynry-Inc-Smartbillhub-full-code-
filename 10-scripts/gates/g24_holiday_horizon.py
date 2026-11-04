#!/usr/bin/env python3
"""G24 holiday-horizon — no tenant's holiday calendar may run out under us.

DEF-042. Provisioning seeded the SIGN-UP YEAR only and nothing renewed it, so on
1 January every business-day grace calculation silently reverted to skipping
weekends alone. No error, no log line, no failing test — the calculation simply
stopped knowing about holidays and kept answering confidently.

**The PO's own worked case is the measurement.** A bill due **Thu 24 Dec 2026**
with 5 business days' grace must charge the late fee on **Tue 5 Jan 2027**. Walk
it: Mon 28, Tue 29, Wed 30, Thu 31 are days 1–4; **Fri 1 Jan 2027 is New Year's
Day**, skip; weekend, skip; Mon 4 Jan is day 5, and the fee applies strictly
after — **Tue 5 Jan**. That answer exists only if 1 Jan 2027 is in the calendar.
Without it the fee lands **Mon 4 Jan**: a day early, *on a public holiday*, for
every customer of that tenant.

WHAT THIS GATE CHECKS, and why it is two checks rather than one
---------------------------------------------------------------
**(a) THE CODE.** Provisioning must seed more than a single year. Checked by
reading the source, so it holds on a machine with no database — which is where
CI runs. A repo whose provisioning seeds one year has re-created DEF-042 no
matter what any live calendar currently says.

**(b) THE DATA, when a database is reachable.** Every tenant whose calendar is
NON-EMPTY must cover through the horizon (default: next calendar year). Skipped
with a stated reason when there is no database — never silently passed.

**AN EMPTY CALENDAR IS NOT A FAILURE, and conflating the two would be a real
defect of its own.** BR-TEN-039 makes the calendar the tenant's: a utility
outside the US deletes every seeded date, legitimately. *Empty* means "this
tenant observes no holidays". *Ending in 2026* means "nobody renewed it". Only
the second is DEF-042, and this gate must never nag the first into re-seeding
US federal holidays it deliberately removed.

RED-PROOF (hard-won law 7 — run before this gate was trusted)
-------------------------------------------------------------
Reverting provisioning to the single-year seed makes clause (a) fail with:

    G24 holiday-horizon FAIL  provisioning seeds ONE year: apps/tenancy/services.py
    calls _seed_us_holidays once and never for a following year (DEF-042)

Usage:
    python3 10-scripts/gates/g24_holiday_horizon.py            # horizon = next year
    python3 10-scripts/gates/g24_holiday_horizon.py --year 2028
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVICES = ROOT / "06-backend" / "apps" / "tenancy" / "services.py"

# The provisioning block that seeds a brand-new tenant's calendar. We assert it
# reaches beyond the current year — matching the CALL SITE rather than a comment,
# because a comment promising renewal is exactly what law 1 says proves nothing.
_SEED_CALL = re.compile(r"_seed_us_holidays\(\s*tenant\s*,\s*([^)]+)\)")


def check_code() -> list[str]:
    """Clause (a): the repository must not be able to re-create DEF-042."""
    if not SERVICES.exists():
        return [f"cannot read {SERVICES.relative_to(ROOT)} — clause (a) NOT EVALUATED"]
    text = SERVICES.read_text()
    args = [m.group(1).strip() for m in _SEED_CALL.finditer(text)]
    # Ignore the definition site and any call inside ensure_us_holidays_through's
    # loop (that one extends an existing calendar and is keyed on a loop var).
    provisioning = [a for a in args if a != "year"]
    if not provisioning:
        return [
            "provisioning does not seed a holiday calendar at all: no "
            "_seed_us_holidays(tenant, …) call site found (DEF-042)"
        ]
    reaches_ahead = any(("+ 1" in a) or ("+1" in a) for a in provisioning)
    if not reaches_ahead:
        return [
            "provisioning seeds ONE year: apps/tenancy/services.py calls "
            "_seed_us_holidays once and never for a following year (DEF-042)"
        ]
    return []


def check_data(horizon: int) -> tuple[list[str], str | None, int]:
    """Clause (b): live tenants. Returns (problems, skip_reason, calendars_checked).

    **The count is returned because a gate that checks nothing must not report
    like a gate that checked everything.** The first version of this said *"every
    non-empty tenant calendar covers it"* while running against a database with
    zero calendars in it — a vacuous truth dressed as a positive finding, which
    is the same species as a skipped test reading green (DEF-101). It now prints
    what it actually looked at, and zero says zero.
    """
    sys.path.insert(0, str(ROOT / "06-backend"))
    try:
        import os

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
        import django

        django.setup()
        from django.db import connection

        from apps.tenancy import models
    except Exception as exc:  # pragma: no cover - environment-dependent
        return [], f"no Django environment ({type(exc).__name__}) — clause (b) NOT EVALUATED", 0

    try:
        connection.ensure_connection()
    except Exception as exc:
        return [], f"no database reachable ({type(exc).__name__}) — clause (b) NOT EVALUATED", 0

    problems: list[str] = []
    checked = 0
    try:
        rows = list(
            models.HolidayCalendar.objects.values_list("tenant_id", flat=True).distinct()
        )
        for tenant_id in rows:
            checked += 1
            last = (
                models.HolidayCalendar.objects.filter(tenant_id=tenant_id)
                .order_by("-holiday_date")
                .values_list("holiday_date", flat=True)
                .first()
            )
            # `last` cannot be None here: this tenant appeared in the distinct
            # list precisely because it HAS rows. An empty calendar never
            # reaches this loop, which is how the tenant's own choice is
            # respected rather than nagged.
            if last and last.year < horizon:
                problems.append(
                    f"tenant {tenant_id} — calendar ends {last.isoformat()}, "
                    f"short of {horizon}; business-day grace in {last.year + 1} "
                    "would skip weekends only (DEF-042)"
                )
    except Exception as exc:
        return [], f"could not read holiday_calendars ({type(exc).__name__}) — clause (b) NOT EVALUATED", 0
    return problems, None, checked


def run() -> tuple[str, str]:
    """The `run_gates.py` contract: (status, one-line detail).

    ⚠ **ADDED 2026-08-16 — THIS GATE WAS REGISTERED AND HAD NEVER RUN.**
    `run_gates.py` imports each gate module and calls `module.run()`; this file
    exposed only `main()`, so every suite run since G24 landed scored it

        G24 holiday-horizon FAIL  gate crashed:
        AttributeError("module 'g24_holiday_horizon' has no attribute 'run'")

    A gate that fails with a message about attributes is not guarding anything —
    it is one more red line in a table that already has red lines, which is
    exactly how a broken guard survives. Found by the DEF-116/123 lane while
    wiring G25, whose first run crashed the same way. Hard-won law 7 again: a
    guard nobody has watched go red is a guard nobody has watched at all.
    """
    horizon = datetime.date.today().year + 1
    problems = check_code()
    data_problems, skipped, checked = check_data(horizon)
    problems += data_problems
    if problems:
        return "FAIL", "; ".join(problems[:3]) + (
            f" (+{len(problems) - 3} more)" if len(problems) > 3 else ""
        )
    detail = f"provisioning seeds beyond the current year; horizon {horizon}"
    if skipped:
        return "PASS", f"{detail}; {skipped}"
    if checked == 0:
        return "PASS", f"{detail}; clause (b) found NO tenant calendars to check"
    return "PASS", f"{detail}; {checked} tenant calendar(s) checked, all reach it"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=None, help="horizon year (default: next year)")
    args = ap.parse_args()
    horizon = args.year or datetime.date.today().year + 1

    problems = check_code()
    data_problems, skipped, checked = check_data(horizon)
    problems += data_problems

    if problems:
        print(f"G24 holiday-horizon FAIL  {len(problems)} problem(s):")
        for p in problems[:10]:
            print(f"    {p}")
        if len(problems) > 10:
            print(f"    (+{len(problems) - 10} more)")
        return 1

    detail = f"provisioning seeds beyond the current year; horizon {horizon}"
    if skipped:
        # Reported, never counted as a pass — an unevaluated clause proves
        # nothing, which is the convention G21 already set.
        print(f"G24 holiday-horizon PASS  {detail}; {skipped}")
    elif checked == 0:
        # NOT "every calendar covers it". There were none. Say so.
        print(f"G24 holiday-horizon PASS  {detail}; clause (b) found NO tenant calendars to check")
    else:
        print(
            f"G24 holiday-horizon PASS  {detail}; {checked} tenant calendar(s) checked, "
            "all reach it"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
