#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 13 — *"Print bills"* (W4), and CR-053's own performance
#           clause (PO 2026-08-31): *"anything added here that runs per account
#           is timed against that figure before it merges"*.
# Rules:    BR-NOT-029 (the print hand-over) · BR-TEN-043 (the instant is an
#           ARGUMENT, never a clock read by the code under test)
# Impacts:  apps/billing/print_set.MEASURED_SECONDS_PER_BILL and
#           MEASURED_STATEMENTS_PER_BILL — this script is where those two
#           numbers come from, and re-running it is how they are moved.
# ───────────────────────────────────────────────────────
"""WHAT ONE BILL COSTS A PRINT SET, MEASURED — never reasoned forwards.

⚠ **THE ONLY THING THIS SCRIPT EXISTS TO PREVENT IS AN INVENTED FIGURE.**
`apps/billing/print_set.py` publishes a per-bill time and a per-bill statement
count, the screen turns the first into *"about four minutes"* and the refusal
turns it into *"it would have taken about 8 minute(s)"*. A number that came from
somebody's intuition would be a sentence the product tells a clerk with nothing
behind it, which is hard-won law 1 wearing a stopwatch.

⚠ **RUN IT ON REAL POSTGRESQL, WITH RLS ENFORCED.** `DEF-2717` is the reason:
the bill run's first published per-account figure was measured with row-level
security BYPASSED and was 25% optimistic. The suite's own settings hardcode
in-memory SQLite (`config/settings/test.py`), so a measurement taken there
describes a database this product does not run on.

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_cr053w4" \\
      python3 10-scripts/cr053_print_set_benchmark.py

It writes the archive to a temporary directory and deletes it, so it can be run
against a check database as often as you like.

WHAT IT REPORTS, AND WHY EACH NUMBER IS THERE
════════════════════════════════════════════════════════════════════════════
  * **seconds per bill** — what the screen's estimate and the oversize refusal
    are both built from.
  * **statements per bill** — `CR-053`'s performance clause asks for exactly
    this: *"at 10,000 accounts one extra query per account is ten thousand more
    statements"*. The bill run's own published figure is ~72 statements an
    account, so a print set's number belongs beside it.
  * **the projection to 1,000 and 10,000**, because a rate is not something a
    person can act on and a number of minutes is.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from apps.billing import print_set  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The instant the archive is stamped with. A CONSTANT, because `BR-TEN-043`
#: makes it an argument and a benchmark that read a clock would be measuring one.
GENERATED_AT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def main() -> int:
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        print("no tenant on this database — seed one first")
        return 2
    core_tenancy.set_current_tenant(tenant.id)

    vendor = connection.vendor
    selection = print_set.print_set_selection({})
    count = selection.count()
    print(f"database: {vendor} · tenant: {tenant.subdomain}")
    if vendor != "postgresql":
        print("⚠ NOT PostgreSQL — this figure does not describe the deployment (DEF-2717)")
    print(f"printable bills: {count}")
    if count == 0:
        print("nothing to measure: this tenant has no issued bill")
        return 2

    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "benchmark.zip"
        # The query count and the wall clock are taken over the SAME call, so
        # the two figures describe one run rather than two.
        with CaptureQueriesContext(connection) as queries:
            started = time.perf_counter()
            result = print_set.build_print_set(
                print_set._iterate(selection), archive, generated_at=GENERATED_AT
            )
            elapsed = time.perf_counter() - started
        size = archive.stat().st_size

    per_bill = elapsed / count
    per_bill_queries = len(queries) / count
    print()
    print(f"  bills considered ......... {result.considered}")
    print(f"  PDFs written ............. {result.pdf_count}")
    print(f"  manifest rows ............ {result.manifest_rows}")
    print(f"  held back ................ {result.held_count}")
    print(f"  pages .................... {result.page_total}")
    print(f"  archive .................. {size:,} bytes ({size / max(1, count):,.0f} a bill)")
    print()
    print(f"  wall clock ............... {elapsed:.3f} s")
    print(f"  SECONDS PER BILL ......... {per_bill:.4f}")
    print(f"  statements ............... {len(queries)}")
    print(f"  STATEMENTS PER BILL ...... {per_bill_queries:.2f}")
    print()
    for population in (1_000, 10_000):
        print(
            f"  {population:>6,} bills → {population * per_bill / 60:6.1f} min · "
            f"{population * per_bill_queries:>9,.0f} statements · "
            f"{population * size / max(1, count) / 1_048_576:6.1f} MiB"
        )
    print()
    print("Put SECONDS PER BILL into apps/billing/print_set.MEASURED_SECONDS_PER_BILL")
    print("and STATEMENTS PER BILL into MEASURED_STATEMENTS_PER_BILL, and record the")
    print("run in 12-governance/02-decision-log.md. Do not reason either forwards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
