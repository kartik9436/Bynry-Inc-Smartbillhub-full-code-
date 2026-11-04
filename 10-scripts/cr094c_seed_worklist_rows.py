"""CR-094-BRC01 step 2 wave C — seed enough worklist rows to SEE an ordering.

⚠ **WHY THIS EXISTS AT ALL.** `BR-CUS-1046` is a statement about which row is
at the top, and step 1 measured that five of the Accounts screen's seven sibling
tabs hold ONE row or NONE on the demo utility: *"With one row or none there is
no position to measure."* A default sort cannot be walked in a browser against a
list of one — every ordering puts the same row first — so a walkthrough over the
seeded tenant as found would report success over code that does nothing.

⚠ **AND THE THING THAT HAS TO BE SPREAD IS `created_at`, NOT THE ROW COUNT.**
`created_at` is `auto_now_add`, so a loop that inserts twelve rows in one
millisecond gives twelve rows at the same instant and *"the newest is first"*
becomes a statement about the tiebreak. `uuid7` ids are themselves time-ordered,
so the walk would have passed either way and proved nothing. Every row below is
stamped a minute apart.

⚠ **AND `received_at` IS SPREAD THE OPPOSITE WAY FROM `created_at`, WHICH IS THE
WHOLE POINT OF THE FIXTURE.** The Requests tab's DEFAULT is now the creation
order and its OVERRIDE is `received_at` — so a seed where the two agree cannot
tell them apart, and a walkthrough over it would report both orderings working
while only one of them did. Row 1 is the newest CREATED and the newest RECEIVED;
row 12 is the oldest of both. So *newest first* must put `SR-CR094-01` at the
top and `sort=received_at&dir=asc` must put `SR-CR094-12` there.

WHAT IT WRITES, and it is the minimum that makes an ordering visible:
  * **service requests** — 12 rows, `SR-CR094-01` the newest … `-12` the oldest.

⚠ **AND WHAT IT DELIBERATELY DOES NOT WRITE, because a seeder that reaches past
its own evidence is worse than a short one.** Move-ins, move-outs, transfers and
disconnects are not rows you can honestly plant: a move-in is *the life of a
`BR-CUS-018` draft account*, a move-out is written by `services.move_out` in one
commit with the terminal status and the agreement end dates, a transfer has two
halves and a counting contract (§5.7.3) three tabs read, and a disconnect case
sits on a ladder with protections. Hand-built rows for any of those would be
shapes the product cannot produce, and a walkthrough over them would prove the
ordering of fiction. **Those four tabs are ordered by the same one shared
helper, and that is asserted in
`06-backend/tests/test_br_cus_1046_lists_open_newest_first.py` against the
queryset's own `ORDER BY` — which is a measurement of the order the database
will apply, not a description of it.** The walkthrough says which tabs it could
and could not see rows on, rather than implying it saw eight.

IT IS RE-RUNNABLE. Rows carry a `SR-CR094-` prefix and are deleted and rewritten
on each run, so it never doubles up and never touches a row it did not write.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://... python3 ../10-scripts/cr094c_seed_worklist_rows.py \\
      [--tenant brazosbend] [--remove]
"""
import argparse
import os
import pathlib
import sys
from datetime import timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.customers import models as customers_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

PREFIX = "SR-CR094-"
COUNT = 12


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--remove", action="store_true", help="delete this script's rows and stop")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        sys.exit(f"no tenant with subdomain {args.tenant!r} on this database")

    with tenant_context(tenant.id):
        gone = customers_models.ServiceRequest.objects.filter(
            tenant=tenant, request_no__startswith=PREFIX
        ).delete()
        print(f"removed {gone[0]} row(s) this script had written before")
        if args.remove:
            return 0

        # ⚠ **THE ROWS MUST BE NEWER THAN THE DEMO SEED'S OWN, NOT MERELY SPREAD
        # (found by the walkthrough, 2026-09-12).** The first draft of this
        # script backdated these twelve by a day each from `now - 13 days`,
        # which spread them correctly and left every one of them OLDER than the
        # six requests `sample_data` writes when the utility is provisioned —
        # all of which carry today's date. So the tab drew `SR-26-0008` at the
        # top, the walkthrough reported *"the newest request is not row one"*,
        # and the ordering was right all along. **A seed that cannot produce the
        # row the assertion names is a false finding waiting to be reported.**
        # Minutes rather than days, anchored at `now`, so row 0 is the newest
        # record on the tenant by a clear margin.
        start = timezone.now()
        for index in range(COUNT):
            # Row 0 is the NEWEST and carries the LOWEST number, so
            # `SR-CR094-01` is what *newest first* must put at the top.
            stamp = start - timedelta(minutes=index)
            request = customers_models.ServiceRequest.objects.create(
                tenant=tenant,
                request_no=f"{PREFIX}{index + 1:02d}",
                state="draft",
                address_as_given=f"{100 + index} Ordering Row",
                applicant_name=f"Sorted, Case {index + 1:02d}",
                # ⚠ **SPREAD THE SAME WAY ROUND AS `created_at` BUT IN DAYS, SO
                # THE TWO ORDERINGS ARE DISTINGUISHABLE AT A GLANCE.** The first
                # draft ran this backwards, which made `SR-CR094-01` both the
                # newest created AND the oldest received — first under BOTH
                # orderings, so the fixture could not tell the default from the
                # override and a walkthrough over it would have reported both
                # working while only one did.
                received_at=start - timedelta(days=index),
            )
            customers_models.ServiceRequest.objects.filter(pk=request.pk).update(
                created_at=stamp
            )
        rows = list(
            customers_models.ServiceRequest.objects.filter(
                tenant=tenant, request_no__startswith=PREFIX
            ).order_by("-created_at")
        )
        print(f"wrote {len(rows)} service requests on {args.tenant}")
        print(f"  newest: {rows[0].request_no}  created {rows[0].created_at:%Y-%m-%d %H:%M}")
        print(f"  oldest: {rows[-1].request_no}  created {rows[-1].created_at:%Y-%m-%d %H:%M}")
        oldest_received = min(rows, key=lambda row: row.received_at)
        print(f"  oldest RECEIVED: {oldest_received.request_no} ({oldest_received.received_at:%Y-%m-%d})")
        print()
        print("# so on the Requests tab:")
        print(f"#   default (newest first) must put {rows[0].request_no} at the very top")
        print(f"#   sort=received_at&dir=asc must put {oldest_received.request_no} first — the")
        print("#   ordering this tab opened on before BR-CUS-1046")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
