#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Walk:    the PO's charge-code walk of 2026-09-19 — *"all rules are set for
#          charge codes - based on services, based on customer class"*.
# Rules:   BR-RAT-108 (`applies_to_customer_classes`, an INCLUSION list where
#          NULL or `[]` means EVERY class) · BR-RAT-088 (`is_base` has its own
#          route) · BR-RAT-730 (`rides_a_periodic_bill`) · CLAUDE.md hard rule 1
# Impacts: two rows on `charges`, both purged by `--purge`. Neither can reach a
#          bill: both are `one_time` with `auto_apply = false`, so
#          `rides_a_periodic_bill` is False for each and R4 neither selects nor
#          refuses them.
# ───────────────────────────────────────────────────────
"""Two probe charge codes, so the two narrowing rules have something to remove.

⚠ **WITHOUT THESE THE WALK CANNOT SEE EITHER RULE WORK, AND THAT IS ITSELF THE
MEASUREMENT.** On the seeded `brazosbend`, of 29 charge codes 5 are `is_base`
and the remaining 24 are ALL service-NULL and class-NULL. `is_base` is
excluded from the plan's charge picker first (`BR-RAT-088`), so every
service-scoped code on the tenant is gone before the service test runs, and no
code carries a customer class at all. Measured 2026-09-19: **the service rule
removes 0 rows and the class rule removes 0 rows on every one of the six
plans.** Both rules are correct and both are inert, so a clerk — or a PO
walking the screen — sees all 24 codes offered on every plan and cannot tell
either rule exists.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://…/sbh \
    JOBS_EAGER=false \
    python3 10-scripts/po20260919_charge_code_walk_probes.py [--purge]

Run it before `po20260919_charge_code_clerk_walk.mjs` and with `--purge`
after. It is idempotent: `get_or_create` on the code, so a second run adds
nothing.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, "06-backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from apps.rating import models as m  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

TENANT = os.environ.get("CHG_WALK_TENANT", "brazosbend")

#: ⚠ **THE PREFIX IS THE PURGE KEY, SO IT MAY NOT COLLIDE WITH A REAL CODE.**
#: `--purge` deletes by it, and a tenant that had genuinely named a code
#: `WALK-…` would lose it. No seeded tenant does; a real one is asked first.
PREFIX = "WALK-"


def main() -> int:
    tenant = tm.Tenant.objects.filter(subdomain=TENANT).first()
    if tenant is None:
        print(f"no tenant {TENANT!r}")
        return 2
    # Hard rule 1 — never touch a tenant table without `app.tenant_id` set.
    # `rating/0038` is the row that taught this module the cost of forgetting:
    # RLS FORCE hid every plan from its backfill and three plans silently lost
    # their customer class (`DEF-RAT-5799`).
    with tenant_context(tenant.id):
        if "--purge" in sys.argv:
            print("purged:", m.Charge.objects.filter(code__startswith=PREFIX).delete())
            return 0
        electric = tm.Service.objects.filter(code="electric").first()
        for code, name, service, classes in [
            # Narrowing rule 1 — the code's own SERVICE.
            (f"{PREFIX}ELEC", "Walk probe — electric only", electric, []),
            # Narrowing rule 2 — `applies_to_customer_classes`.
            (f"{PREFIX}COMM", "Walk probe — commercial only", None, ["commercial"]),
        ]:
            row, created = m.Charge.objects.get_or_create(
                tenant_id=tenant.id,
                code=code,
                defaults=dict(
                    name=name,
                    # `one_time` + `auto_apply=False` is the pair that makes
                    # these inert: `rides_a_periodic_bill` returns False, so
                    # R4 skips them rather than pricing OR refusing.
                    charge_type="one_time",
                    auto_apply=False,
                    service=service,
                    applies_to_customer_classes=classes,
                    amount_rule="flat",
                    amount=Decimal("11.0000"),
                    is_base=False,
                    taxable_default=False,
                    waivable=False,
                    separate_line=False,
                ),
            )
            svc = service.code if service is not None else None
            print(f"{code} created={created} service={svc} classes={classes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
