# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 task `P2.11` — *"Notification: the unclosed till. Tells
#          a supervisor; never closes"* (PO ruling 2026-09-23 §3.1).
# Rules:   CLAUDE.md hard rule 1 (the sweep enters each tenant's context;
#          `counter_sessions` is under FORCE ROW LEVEL SECURITY) · BR-TEN-074
#          (per-tenant context, failures isolated) · BR-TEN-081 (the utility's
#          OWN clock decides what day it is) · BR-TEN-043 (a business date is an
#          input — `--day` is how a human names one) · BR-NOT-020/021
# Tests:   06-backend/tests/test_cr136_p2_10_11_wire.py
# ───────────────────────────────────────────────────────
"""`manage.py sweep_open_counters` — tell a supervisor which tills nobody closed.

**IT TELLS. IT NEVER CLOSES.** PO ruling 2026-09-23 §3.1: *"no auto-close. A
System Admin closes it."* This command queues one in-app message per tenant and
writes nothing at all to `counter_sessions`. The blueprint's midnight
auto-close (`P2.18`) was struck and no scheduled job may seal a till.

WHICH TILLS IT NAMES
--------------------
Those opened before the swept day began and still `closed_at IS NULL`. A till
opened at 08:55 and still open at 23:00 the same day is a clerk at work; one
open since yesterday is the thing a supervisor has to act on, because under
§3.1 its owner cannot open a second one and therefore **cannot take money this
morning**. `apps/payments/counter_watch.py` argues the boundary at length.

THE DAY, AND WHOSE CLOCK IT IS ON
---------------------------------
`--day` names the banking day to sweep — the morning whose supervisor is being
told. Left out, each tenant is swept for **its own today** (BR-TEN-081,
`tenancy.selectors.tenant_today`), resolved inside that tenant's context, so a
utility in Houston and one in Honolulu are not swept for the same date merely
because one server ran the job.

The cut-off handed to the sweep is a MOMENT — midnight of that day in the
tenant's timezone — never a truncated `opened_at::date`, which is `OQ-153`.

EXIT CODES
----------
  0  the sweep ran (or had nothing to tell) and every targeted tenant succeeded
  1  refused before any tenant was touched — an unknown `--tenant`, a bad --day
  2  the sweep RAN and at least one tenant FAILED; the failures are named and
     the tenants that succeeded keep their result (BR-TEN-074)

⚠ **IT IS SCHEDULED NOW — AMENDED 2026-09-23 (`DEF-PAY-6268`).** This passage
read: *"NOT SCHEDULED BY THIS LANE. This repo carries no beat schedule to add it
to … Until it is scheduled, `P2.11`'s outcome (*"nobody has to notice a missing
count by looking"*) is true of anyone who runs this and not yet true on its
own."* The first clause was true and **the second was false the day it was
written** — five beat entries were already installed from five
`AppConfig.ready()` methods, the nearest of them
(`payments.collections_ladder`) in this very app. So the sentence read as a
deployment decision somebody else would make, and nobody made it: the notice
fired never, and the cost the PO accepted in §3.1 had no upper bound.

`apps/payments/counter_watch_schedule.py` now fires the same sweep **once a
morning at 06:00 on each utility's own clock**, and `PaymentsConfig.ready()`
installs the entry. **This command is unchanged and is still the operator's** —
it is how a person sweeps a named `--tenant`, re-runs a named `--day` after a
broker outage, or gets the clean answer on a morning when every counter was
closed (the unattended sweep is deliberately silent then). Running it after the
schedule has already run that banking day cannot produce a second message:
`counter_watch.sweep_id` is a `uuid5` of the utility and the day.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core import tenancy as tenancy_kernel

from apps.payments import counter_watch
from apps.tenancy import models, selectors


class Command(BaseCommand):
    help = (
        "Tell a supervisor which counters were left open. Queues one in-app "
        "message per tenant (BR-NOT-020) and closes nothing — a System Admin "
        "force-closes a till, never a job (PO ruling 2026-09-23)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--tenant",
            dest="subdomain",
            default=None,
            help="Sweep one tenant by subdomain. Default: every tenant.",
        )
        parser.add_argument(
            "--day",
            dest="day",
            default=None,
            help=(
                "The banking day to sweep, YYYY-MM-DD. Default: each tenant's own "
                "today, on its own clock (BR-TEN-081)."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain = options.get("subdomain")
        tenants = models.Tenant.objects.all().order_by("subdomain")
        if subdomain:
            tenants = tenants.filter(subdomain=subdomain)
            if not tenants.exists():
                raise CommandError(f"no tenant with subdomain {subdomain!r}")

        named_day: dt.date | None = None
        if options.get("day"):
            try:
                named_day = dt.date.fromisoformat(str(options["day"]))
            except ValueError as bad:
                raise CommandError(
                    f"--day {options['day']!r} is not a date. Use YYYY-MM-DD; the day is "
                    "an input and never a clock (BR-TEN-043)."
                ) from bad

        # The day and its midnight are resolved PER TENANT and inside that
        # tenant's context, because `tenant_today` and `tenant_timezone` read
        # that tenant's own Regional setting. Resolved here rather than inside
        # the sweep so `counter_watch` reads no clock at all and stays testable
        # against a fixed moment.
        tenant_days = []
        for tenant in tenants:
            with tenancy_kernel.tenant_context(tenant.id):
                zone = selectors.tenant_timezone()
                day = named_day or selectors.tenant_today()
            # Midnight of that day ON THE UTILITY'S OWN CLOCK. A MOMENT, so
            # nothing here truncates a stored timestamp to a date (OQ-153).
            cutoff = dt.datetime.combine(day, dt.time.min, tzinfo=zone)
            tenant_days.append((tenant.id, cutoff, day))

        # ONE moment for the whole run, read HERE — the single place in this
        # feature that touches a wall clock, so the sweep and the seam below it
        # both take it as a parameter (BR-TEN-043, and G6 greps for the read).
        finished_at = timezone.now()
        result = counter_watch.sweep(tenant_days, finished_at=finished_at)

        self.stdout.write(result.sentence())
        for row in result.by_tenant:
            if row.still_open:
                codes = ", ".join(str(out.get("code")) for out in row.outcomes) or "no outcome"
                self.stdout.write(
                    f"  tenant {row.tenant_id} · {row.day.isoformat()}: "
                    f"{row.still_open} of {row.open_at_cutoff} still open — {codes}"
                )
        if result.failed:
            for tenant_id, kind in result.failed.items():
                self.stderr.write(f"tenant {tenant_id} failed: {kind}")
            raise CommandError(
                f"{len(result.failed)} tenant(s) failed; the rest were swept",
                returncode=2,
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-136-BRC07 §3.1 + task `P2.11` · apps/payments/counter_watch.py · apps/audit/management/commands/sweep_error_diagnostics.py (the per-tenant sweep precedent this follows, down to the exit codes) · apps/tenancy/selectors.tenant_today + tenant_timezone (BR-TEN-081)
# generated: 2026-09-23 by lane P2-WIRE
# checklist: A✔ B=deferred(a management command draws nothing) C✔ D=deferred(no endpoint) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) IT CLOSES NOTHING — PO ruling 2026-09-23 §3.1. (2) [AMENDED 2026-09-23, DEF-PAY-6268] IT IS SCHEDULED — `apps/payments/counter_watch_schedule.py` fires the same sweep at 06:00 on each utility's own clock and `PaymentsConfig.ready()` installs the entry. This exception read *"IT IS NOT SCHEDULED by this lane; there is no beat schedule in this repo"*, and the second half was false when written: five entries were already installed from five `ready()` methods. The command stays the operator's by-hand path. (3) THE ONE CLOCK READ IS HERE, once per run, and is passed down — so `counter_watch` and `run_alert_seam` read none (BR-TEN-043).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
