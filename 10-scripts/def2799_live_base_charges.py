#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2799 — the fix writes `tariff_versions.base_charge`, a column the
#          LIVE path reads (`gather._base_charge_for`). "It cannot move a bill"
#          is therefore a claim about money and hard-won law 1 forbids leaving
#          a claim about money in a comment: *"a comment claiming a guarantee is
#          not the guarantee."* This is the guarantee.
# Rules:   BR-BIL-039 (the preview and the real run are the SAME code, so this
#          reads `prepare_run`'s own output) · BR-RAT-087 (the server formats
#          money; nothing here re-rounds one) · CLAUDE.md hard rule 1
# Impacts: nothing. It writes no row — `prepare_run` writes nothing by its own
#          contract and the pass is additionally rolled back.
# ───────────────────────────────────────────────────────
"""What the LIVE path resolves as each account's per-service BASE CHARGE.

Run it BEFORE a change to the tenant's rate configuration and AFTER, and diff
the two outputs. Anything other than an empty diff means a customer's base
charge moved, which for `DEF-2799` is the one outcome that is not allowed.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://…/<db>?sslmode=disable \
    JOBS_EAGER=false \
    python3 10-scripts/def2799_live_base_charges.py > before.txt

⚠ **IT PRINTS EVERY ACCOUNT, NOT A TOTAL.** A total can be preserved by two
errors that cancel — one account up $7.00 and another down $7.00 sums to no
change at all — and the whole point of this file is that it cannot be satisfied
that way. The total is printed as well, at the end, because that is the figure a
person quotes.

It also prints, by name, every account the run BLOCKED and why: an account that
stops being billable is a bill that moved to zero, and a check that only looked
at the accounts still present would report success over exactly that.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

settings.DEBUG = False

from apps.billing import runs  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
SERVICE_DATE = date(2026, 7, 1)


def _money(amount: Decimal) -> str:
    """CLAUDE.md hard rule 2 — money DISPLAYS at 2 decimals. No B4 rule is
    applied: every figure here is a stored base charge already exact at 2dp, and
    one that is not is printed unrounded and named rather than quietly rounded."""
    value = Decimal(str(amount))
    two = value.quantize(Decimal("0.01"))
    return f"${two}" if two == value else f"${value} (NOT exact at 2dp — unrounded)"


class _Done(Exception):
    def __init__(self, lines, total, rows):
        super().__init__("done")
        self.lines, self.total, self.rows = lines, total, rows


def main() -> int:
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        raise SystemExit("no tenant on this database")

    try:
        with transaction.atomic():
            lines: list[str] = []
            total = Decimal("0")
            rows = 0
            with core_tenancy.tenant_context(tenant.id):
                for cycle in metering_models.Cycle.objects.order_by("code"):
                    prepared = runs.prepare_run(
                        cycle_id=cycle.id,
                        period_start=PERIOD_START,
                        period_end=PERIOD_END,
                        service_date=SERVICE_DATE,
                    )
                    for data in sorted(prepared.ready, key=lambda d: d.account_no):
                        for config in sorted(data.tariffs, key=lambda c: c.service):
                            if config.base_charge is None:
                                lines.append(
                                    f"{data.account_no}  {config.service:<12} "
                                    "NO BASE STATED"
                                )
                                continue
                            amount = Decimal(str(config.base_charge))
                            lines.append(
                                f"{data.account_no}  {config.service:<12} {_money(amount)}"
                            )
                            total += amount
                            rows += 1
                    for problem in sorted(prepared.blocked, key=lambda p: p.reason):
                        lines.append(f"BLOCKED  {cycle.code}  {problem.reason}")
            raise _Done(lines, total, rows)
    except _Done as done:
        lines, total, rows = done.lines, done.total, done.rows

    blocked = Counter(line for line in lines if line.startswith("BLOCKED"))
    for line in lines:
        if not line.startswith("BLOCKED"):
            print(line)
    print("─" * 60)
    for line, count in sorted(blocked.items()):
        print(f"{line}  x{count}")
    print("─" * 60)
    print(f"{rows} base-charge row(s) · {_money(total)} in total for {PERIOD_START}–{PERIOD_END}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2799 · CR-052 task 20
# generated: 2026-08-31 by the DEF-2799/DEF-2798 lane (claude)
# gates: reads only; `prepare_run` writes nothing and the pass is rolled back.
# ──────────────────────────────────────────────────────────
