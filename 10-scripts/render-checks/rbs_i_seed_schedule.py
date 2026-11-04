#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-RBS-007 (EP-RBS-03) — CR-075 wave I task I7, the seed half.
# Rules:   BR-RBS-016 (the tenant's clock; a missed firing raises) ·
#          CLAUDE.md hard rule 1 (tenant context before any tenant table) ·
#          hard-won law 6 (diff the running app against the design)
# Tests:   the browser half is 10-scripts/render-checks/rbs-i-the-clock.mjs
# ───────────────────────────────────────────────────────
"""Put a real schedule on a real tenant, advance the clock, and let the sweep run.

⚠ **THE WHOLE POINT IS THAT NOBODY PRESSES ANYTHING.** `EP-RBS-03`'s exit test
is *"nobody opens the product"*, and a walkthrough that started the run itself
would be proving the wrong thing. This script sets a schedule, moves the clock
the sweep is given, and calls the sweep — the same function the beat entry calls
once a minute — and then the browser half opens the product and reads what is
there. No run is opened by hand anywhere in either file.

⚠ **`JOBS_EAGER` IS THE ONE PIECE OF STAGE MACHINERY AND IT IS NAMED RATHER
THAN HIDDEN.** In production the sweep enqueues and a worker on `-Q runbooks`
runs the body minutes later. Under `config.settings.local` with `JOBS_EAGER`
true, `core.jobs.enqueue` dispatches in-process, so the run finishes before this
script returns and the browser has something to read a second later. That is the
same code path with the broker taken out, not a different one: `run_scheduled_job`
is the body either way.

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
      python3.12 10-scripts/render-checks/rbs_i_seed_schedule.py --tenant brazosbend
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.runbooks import models, scheduler  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

CHICAGO = "America/Chicago"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--key", default="configuration_check")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"no tenant {args.tenant!r}")
        return 2

    with core_tenancy.tenant_context(tenant.id):
        runbook = models.Runbook.objects.filter(key=args.key).first()
        if runbook is None:
            print(f"tenant {args.tenant} has no runbook {args.key!r} — run seed_demo first")
            return 2

        # ── the schedule a clerk would type: Daily 06:00, their own zone ─────
        models.Runbook.objects.filter(pk=runbook.pk).update(
            enabled=True,
            trigger_kind=models.TRIGGER_SCHEDULE,
            cron="0 6 * * *",
            timezone=CHICAGO,
        )
        runbook.refresh_from_db()
        tz = scheduler.zone(CHICAGO)

        # ── clear this runbook's scheduled history so the walk is repeatable ─
        # Only the SCHEDULED rows, and only this runbook's: a manual run some
        # other lane started is somebody else's evidence.
        models.RunbookRun.objects.filter(
            runbook_id=runbook.pk, trigger=models.TRIGGER_SCHEDULE
        ).delete()

        # ⚠ **THE SCHEDULE IS BACKDATED FOUR DAYS, AND THE FIRST DRAFT GOT
        # THIS WRONG TWICE.** Draft one moved the sweep's CLOCK forward and
        # produced a missed firing dated in the FUTURE — a row a clerk would
        # read as a morning that has not happened yet, dressed as one that
        # failed. Draft two moved the clock BACKWARD and found nothing at all,
        # because the anchor is the latest of the last scheduled run, the last
        # schedule edit and the runbook's own `created_at`, and `created_at` was
        # later than the clock. **The anchor is what has to move, not the
        # clock**, so the runbook is dated four days ago and the sweep runs on
        # the real one.
        models.Runbook.objects.filter(pk=runbook.pk).update(
            created_at=scheduler._utcnow() - timedelta(days=4)
        )
        runbook.refresh_from_db()

        now = scheduler._utcnow()
        next_run = scheduler.next_run_at(runbook, now=now)
        print(f"── next run   : {next_run.isoformat()} "
              f"= {next_run.astimezone(tz).strftime('%Y-%m-%d %H:%M %Z')}")

        # ── ONE SWEEP, BOTH OUTCOMES. The clock is one minute past the most
        #    recent 06:00 that has already gone by: that firing is DUE, and the
        #    three mornings before it are MISSED. Under JOBS_EAGER the due run's
        #    body executes before this returns.
        spec = scheduler.parse_cron("0 6 * * *")
        last_fire = None
        for fire in scheduler.fires_between(
            spec, tz, after=now - timedelta(days=4), until=now
        ):
            last_fire = fire
        clock = last_fire + timedelta(minutes=1)
        print(f"── sweep clock: {clock.astimezone(tz).strftime('%Y-%m-%d %H:%M %Z')}")
        outcome = scheduler.sweep(now=clock)
        print(f"── missed run : raised for {outcome['raised']}")
        print(f"── due run    : enqueued {len(outcome['enqueued'])} job(s)")

        rows = list(
            models.RunbookRun.objects.filter(
                runbook_id=runbook.pk, trigger=models.TRIGGER_SCHEDULE
            ).order_by("-started_at")
        )
        for row in rows:
            when = (
                row.started_at.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
                if row.started_at
                else "—"
            )
            print(f"   {row.status:<8} started {when}  version {row.version}")
        print(f"── SMOKE_RUNBOOK_KEY={runbook.key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-007 (EP-RBS-03; CR-075 wave I task I7)
# generated: 2026-09-07 by the CR-075 wave I build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a(this is a seeder) F✔ G✔ H=n/a
# gates: run by hand before the browser half; see rbs-i-the-clock.mjs
# exceptions: it reaches `scheduler._utcnow` and `scheduler.sweep(now=…)`, which are the module's own — a seeder that duplicated the clock would prove a different scheduler
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
