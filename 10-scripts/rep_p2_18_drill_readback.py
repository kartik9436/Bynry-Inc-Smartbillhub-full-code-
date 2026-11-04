#!/usr/bin/env python3
"""`P2.18`'s drill-through, proved by EFFECT against a real seeded utility.

WHY THIS IS A SCRIPT AND NOT A pytest CASE
------------------------------------------
It was a pytest case first, gated on `connection.vendor == "postgresql"`, and
it was **incapable of passing** — CLAUDE.md hard-won law 7's third shape.
pytest-django builds its own empty `test_` database, so a case pointed at it
finds no tenant and no receivable to count; and the default suite is in-memory
SQLite, which has neither. Both ways of running it were impossible, in opposite
directions. Weakening it to a `pytest.skip` would have been a false pass, so it
moved here, where it is run against a seeded clone:

    ./10-scripts/proof-db.sh clone p218
    DATABASE_URL=... PYTHONPATH=06-backend \\
      06-backend/.venv/bin/python 10-scripts/rep_p2_18_drill_readback.py

WHAT IT PROVES, AND WHAT IT PROVED BEFORE THE FIX
-------------------------------------------------
For every group row a report emits, it replays that row's `filters` through the
SAME runner and compares the row COUNT with the group's own `rows`. That is the
only assertion that tells a working drill-through from a broken one — a shape
assertion over the `path` passes either way, which is exactly how `DEF-REP-6869`
survived `tests/test_rep_p2_17_slicers.py`.

It also replays the `path` verbatim, the way `P2.18` would have been built if
the sibling's claim that *"the path IS the filter set"* had been taken on trust,
and prints BOTH counts side by side — so the difference is a number on screen
rather than a sentence in a report.
"""

from __future__ import annotations

import os
import sys

import django


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    django.setup()

    from apps.reports import runner
    from apps.tenancy.models import Tenant
    from core.tenancy import tenant_context

    tenant = Tenant.objects.first()
    if tenant is None:
        print("FAIL: no tenant in this database — nothing to count, which is not a pass")
        return 2

    report, level = "ar_aging", "consumer_class"
    failures = 0
    with tenant_context(tenant.id):
        payload = runner.run(report, {"group_by": level}).payload
        groups = [row for row in payload["rows"] if row.get("__kind__") == "group"]
        if not groups:
            print(f"FAIL: {report} grouped by {level} produced no group rows")
            return 2
        print(f"{report} · group_by={level} · {len(groups)} group(s)\n")
        for group in groups:
            filters = group.get("filters")
            path = {step["dimension"]: step["value"] for step in group["path"]}
            by_path = runner.run(report, dict(path)).payload
            path_rows = len([r for r in by_path["rows"] if r.get("__kind__") != "group"])
            # ⚠ **THE DROPPED LIST IS THE WHOLE POINT OF PRINTING THIS LINE.**
            # `runner.bind` discards a parameter the dataset does not declare,
            # so replaying the path returns the report UNFILTERED — and on a
            # tenant with ONE group that is the same number as the group's own,
            # which reads as a perfect match. It is the entire report under a
            # chip naming one group. Printing the count alone would have
            # reported success over the defect this script exists to show.
            ignored = runner.dropped(runner.resolve(report), dict(path))
            print(f"  group {group['value']!r} · subtotal covers {group['rows']} rows")
            print(f"    the PATH replayed verbatim  {path!r:48} -> {path_rows} rows"
                  + (f"   ⚠ {list(ignored)} DROPPED — this is the WHOLE report"
                     if ignored else ""))
            if not filters:
                print(f"    no drill-through offered   ({group.get('drill_unavailable')})")
                continue
            back = runner.run(report, dict(filters)).payload
            rows = len([r for r in back["rows"] if r.get("__kind__") != "group"])
            ok = rows == group["rows"]
            print(f"    the FILTERS replayed        {dict(filters)!r:48} -> {rows} rows  "
                  f"{'MATCH' if ok else 'MISMATCH'}")
            if not ok:
                failures += 1
    print("\n" + ("PASS" if failures == 0 else f"FAIL: {failures} group(s) do not reproduce"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
