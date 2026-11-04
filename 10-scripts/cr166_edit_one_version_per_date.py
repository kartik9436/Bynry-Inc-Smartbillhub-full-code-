"""CR-166-BRC10 round 3 task 7 — after the EDIT form's two version-making saves,
does billing get exactly ONE discount version per date? Read on PostgreSQL 16,
through the product's own resolver, over the discounts the browser walk
(`cr166_edit_discount_walk.mjs`) saved through the screen.

  * SRB… — *New value from a date*: 15 % from 08/01/2026, 12 % from 01/01/2027.
  * SRC… — *Fix a mistake*: v1 15 % superseded and kept, v2 1.5 % over the same
    window.

For every day 12/25/2026–01/05/2027 it counts the versions whose status prices
(`active`) and whose window holds that day, and asks `active_version` — the call
`discount_rules_for_account` makes for the bill — which refuses rather than
picks when two are in force (`two_versions_in_force`). It writes nothing.

RUN IT:
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_disc_edit JOBS_EAGER=false \\
      python ../10-scripts/cr166_edit_one_version_per_date.py SRB72040 SRC72040
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db.models import Q  # noqa: E402

from apps.rating import discount_services  # noqa: E402
from apps.rating import discounts as dm  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SUBDOMAIN = os.environ.get("SEED_TENANT", "brazosbend")
BILL = Decimal("60.00")


def main(codes: list[str]) -> int:
    tenant = Tenant.objects.get(subdomain=SUBDOMAIN)
    failures = 0
    with core_tenancy.tenant_context(str(tenant.id)):
        for code in codes:
            discount = dm.Discount.objects.get(code=code)
            print(f"\n{code}:")
            for v in dm.DiscountVersion.objects.filter(discount=discount).order_by("version_no"):
                print(f"  v{v.version_no} {v.status:<10} {v.value:>10} {v.effective_from} – {v.effective_to or 'no end'}")
            day = date(2026, 12, 25)
            while day <= date(2027, 1, 5):
                in_force = dm.DiscountVersion.objects.filter(
                    discount=discount,
                    status=dm.VERSION_ACTIVE,
                    effective_from__lte=day,
                ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
                count = in_force.count()
                chosen = discount_services.active_version(discount, day)
                off = (BILL * chosen.value / 100).quantize(Decimal("0.01")) if chosen else None
                ok = count == 1 and chosen is not None
                failures += 0 if ok else 1
                print(
                    f"  {day:%m/%d/%Y}  versions in force: {count}  billing reads v{chosen.version_no if chosen else '-'}"
                    f"  {chosen.value.normalize() if chosen else '-'}% → −${off} off ${BILL}  {'OK' if ok else 'FAIL'}"
                )
                day += timedelta(days=1)
    print(f"\n{'EXACTLY ONE VERSION PER DATE' if failures == 0 else f'{failures} DATE(S) WRONG'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
