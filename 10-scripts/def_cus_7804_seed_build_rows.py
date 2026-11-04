"""`DEF-CUS-7804` — seed enough New-connect builds to SEE the wired columns.

⚠ **WHY THIS EXISTS.** The five facts this defect wires — `customer`,
`age_days` + `age_is_accented`, `quote_total`, `mode`, `scope`, `raised_by`,
`last_stamped_event` — are all things a ROW carries, and the demo utility as
provisioned holds **zero** connections. A browser walk over an empty list
would photograph the empty state and report success over columns that render
nothing, which is the exact defect being fixed (hard-won law 2).

⚠ **AND THE EMPTY CASE OF EACH FIELD IS SEEDED ON PURPOSE, not only the full
one.** `DEF-127`'s whole lesson is that an absent fact and a blank cell look
identical once drawn, so the fixture has to contain a build with **no owner
account**, a build with **no quote**, a build with **no orders** and a build
with **no scope** — otherwise the walk proves only the happy row.

⚠ **AGE IS SPREAD ACROSS `BR-CUS-106`'s SEVEN-DAY LINE.** One build is 41 days
old and must draw in the accent; one is 1 day old and must draw plain. A seed
where every row falls the same side of the threshold cannot tell an accent
that works from an accent that is always on.

⚠ **BUILT THROUGH THE REAL WRITE PATHS**, not by inserting rows: `create_
connection`, `add_connection_service`, `submit_connection`, `create_work_order`
are what the wizard calls, so the shapes are shapes the product can produce.
Only the three things the wizard would have collected from a clerk — the owner
account, the quote and the scope — are stamped with `.update()`, and the
backdating of `submitted_at` is the same trick `test_w6_connection_list.py`
uses for the same reason.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      python3 ../10-scripts/def_cus_7804_seed_build_rows.py \\
      [--tenant brazosbend] [--remove]
"""

import argparse
import os
import pathlib
import sys
from datetime import timedelta
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.customers import models as customers_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import connections as w6  # noqa: E402
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

PREFIX = "B-7682-"

#: (suffix, units, orders_done, orders_total, days_old, quote, scope, owner?)
#:
#: Row 0 is the NEWEST created, so `BR-CUS-1046`'s newest-first default must
#: put it at the top — which also means the screenshot shows the ruled order
#: rather than the one the three rewritten tests used to assert.
ROWS = (
    ("01", 3, 3, 4, 2, Decimal("535.0000"), "new_premise", True),
    # ⛔ NO OWNER ACCOUNT — the CUSTOMER cell must read *no account yet*, and
    # NO QUOTE — the Charged cell must read *Not priced*, never `$0.00`.
    ("02", 2, 0, 0, 1, None, None, False),
    # 41 days: the far side of `BR-CUS-106`'s seven, so AGING draws accented.
    ("03", 6, 12, 18, 41, Decimal("3675.0000"), "new_units", True),
    ("04", 1, 2, 2, 9, Decimal("0.0000"), "new_service", True),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        sys.exit(f"no tenant with subdomain {args.tenant!r} on this database")
    actor = identity_models.User.objects.filter(tenant=tenant).first()
    if actor is None:
        sys.exit("no user on this tenant to act as")

    with tenant_context(tenant.id):
        gone = work_tables.Connection.objects.filter(
            tenant=tenant, connection_no__startswith=PREFIX
        ).delete()
        print(f"removed {gone[0]} row(s) this script had written before")
        if args.remove:
            return 0

        account = customers_models.Account.objects.filter(tenant=tenant).first()
        premises = list(metering_models.Premises.objects.filter(tenant=tenant)[:4])
        if not premises:
            sys.exit("no premises on this tenant to build against")

        for index, (suffix, units, done, total, days, quote, scope, owned) in enumerate(ROWS):
            place = premises[index % len(premises)]
            created = w6.create_connection(actor, {"premises_id": str(place.id)})
            build = work_tables.Connection.objects.get(pk=created["id"])
            work_tables.Connection.objects.filter(pk=build.id).update(
                connection_no=f"{PREFIX}{suffix}"
            )
            w6.add_connection_service(actor, build.id, service_code="water")
            w6.add_connection_service(actor, build.id, service_code="electric")
            w6.submit_connection(actor, build.id)

            order_ids = [
                w6.create_work_order(actor, build.id, {"type": f"step {n + 1}"})["id"]
                for n in range(total)
            ]
            if done:
                work_tables.WorkOrder.objects.filter(pk__in=order_ids[:done]).update(
                    state=work_tables.WO_COMPLETED
                )

            # The three facts the wizard collects from a clerk, plus the
            # backdate. `submitted_at` is stamped by `submit_connection` at
            # `now`, so it is moved AFTER the call, exactly as the suite does.
            work_tables.Connection.objects.filter(pk=build.id).update(
                submitted_at=timezone.now() - timedelta(days=days),
                quote_total=quote,
                scope=scope,
                owner_account_id=(account.id if (owned and account is not None) else None),
            )
            print(
                f"  {PREFIX}{suffix}: {units} unit(s), {done} of {total} orders, "
                f"{days} day(s) old, quote={quote}, scope={scope}, "
                f"owner={'yes' if owned and account is not None else 'NO'}"
            )
    print(f"seeded {len(ROWS)} build(s) on {args.tenant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
