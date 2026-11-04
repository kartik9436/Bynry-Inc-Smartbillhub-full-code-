"""`CR-131-BRC07` STEP 1 — THE GATE, PROVED BY MOVING A ROUTE AND ASKING EVERY SURFACE.

WHY THIS EXISTS
---------------
`CR-131-BRC07` §4 makes one thing a gate before any of the route-derivation work
is built: *"Prove a collected read keeps its route under derivation … If it
cannot be proved, STOP and re-open the ruling with that fact — never work around
it."* The rule under test is **`BR-MET-081`** — *"Changes take effect next read
window. Collected reads keep their route."* — which the wizard prints on screen
and `services.update_route` asserts in its docstring: *"touches no `meter_reads`
row at all"*.

**Reading the code is not proof, and here the code is TRUE and the promise is
still broken**, which is hard-won law 1's exact shape. So this MOVES a route's
premises through the product's own service call and asks every surface that
answers *"which reads belong to this route"*, before and after.

WHAT IT ESTABLISHES — three things, and the second is why the lane stopped
--------------------------------------------------------------------------
1. **The stamp is safe.** `meter_reads.route_id` (`BR-MET-079`, `metering/0012`)
   is written once by `collection_route_id` at collection and nothing in the
   codebase updates it. The move leaves every stamp in place.
2. **`BR-MET-081` is NOT KEPT ON ANY SCREEN A CLERK READS** (`DEF-MET-6143`).
   Four of the five surfaces resolve the route through
   `asset__service_point__route_id` — the LIVE membership projection — so a
   hundred reads collected on one route leave its reads list, its progress, its
   sheet and its last-read date the instant its premises move, and the receiving
   route inherits them. Only the delete guard reads the stamp.
3. **The stamp's ONLY source is `service_points.route_id`** (section B below).
   A derivation design that stops maintaining that stored projection stops
   stamping new reads: `collection_route_id` returns `None`, the column is
   nullable, its own docstring calls NULL *"honest"*, and **nothing goes red**.

⚠ **IT WRITES NOTHING.** Both halves run inside `transaction.atomic()` and abort
by raising, so the fixture is not moved; section A re-asks the surfaces after the
rollback to show that. Run it on an isolated clone anyway
(`10-scripts/proof-db.sh clone <label>`), never on a database a sibling is using.

⚠ **IT MUST RUN ON REAL POSTGRESQL, NOT THE DEFAULT SUITE** (CLAUDE.md law 14):
`config/settings/test.py` hardcodes in-memory sqlite, and the whole point here is
what a real transaction and a real RLS-scoped connection do.

WHAT WOULD MAKE THIS PASS WRONGLY
---------------------------------
Asking only the delete guard, which is the one surface that reads the stamp and
therefore the one that cannot show the defect. Every surface is asked by CALLING
the function the screen calls, never by re-writing its query here — a second copy
of a query proves the copy.

HOW TO RUN IT
-------------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_<label> \
      python3 manage.py shell < ../10-scripts/cr131_br_met_081_gate_probe.py

MEASURED OUTPUT, `brazosbend` seeded on a clone of pinned tip `cb2757596`,
2026-09-22, product 2.322.1 — 516 collected reads, all 516 stamped:

    RT-009 'Cedar Ridge — monthly walk' service=water premises=8 members=9

    BEFORE THE MOVE
      RT-009      stamp= 100 | readslist= 100 progress= 100 sheet=  18 deleteguard= 100 points= 18 last=2026-08-12
      RT-001      stamp=   8 | readslist=   8 progress=   8 sheet=   3 deleteguard=   8 points= 22 last=2026-08-01
    AFTER moving RT-009's premises onto RT-001
      RT-009      stamp= 100 | readslist=   0 progress=   0 sheet=   0 deleteguard= 100 points=  0 last=None
      RT-001      stamp=   8 | readslist= 100 progress= 100 sheet=  18 deleteguard= 108 points= 18 last=2026-08-12

    B · collection_route_id WITH the point stamped    : 01a0c23c-…-bdde2d1a8913 (RT-009)
        collection_route_id WITHOUT any point stamp   : None
        -> a read collected now would be stamped route_id=None
"""

from types import SimpleNamespace

from django.db import transaction

from apps.assets import models as assets_models
from apps.identity import models as ident
from apps.metering import models as met
from apps.metering import route_sheet, selectors, services
from apps.tenancy import models as ten
from core import tenancy

#: Named by SUBDOMAIN and looked up, because an id hardcoded into a script is the
#: first thing to rot when a fixture is reseeded.
TENANT = "brazosbend"
#: The subject route. Any ACTIVE route with collected reads works; this one is
#: the seeded fixture's largest read history.
SUBJECT = "RT-009"


class Rollback(Exception):
    """Raised to abort the atomic block once the result has been printed."""


def surfaces(route_id, label: str) -> None:
    """Every surface that answers *"which reads belong to this route"*, asked by
    CALLING what the screen calls. `stamp` and `deleteguard` read
    `meter_reads.route_id`; the rest resolve through `service_points.route_id`."""
    reads_list = selectors.read_list(filters={"route": str(route_id)}, include_archive=True).count()
    progress = services.collected_read_count_impl(route_id=route_id)
    last = services.last_read_completion_impl(route_id)
    try:
        sheet = len(
            [m for stop in route_sheet.route_sheet_data(route_id)["stops"] for m in stop["meters"]]
        )
    except Exception as exc:  # a sheet that cannot render is a result, not a crash
        sheet = f"ERR {type(exc).__name__}"
    print(
        f"  {label:12s} stamp={met.MeterRead.objects.filter(route_id=route_id).count():4} | "
        f"readslist={reads_list:4} progress={progress:4} sheet={str(sheet):>4} "
        f"deleteguard={services.route_read_history_count(route_id):4} "
        f"points={met.ServicePoint.objects.filter(route_id=route_id).count():3} "
        f"last={last and last.date()}"
    )


tenant_id = str(ten.Tenant.objects.get(subdomain=TENANT).id)
with tenancy.tenant_context(tenant_id):
    src = met.Route.objects.get(code=SUBJECT)
    user = ident.User.objects.order_by("email").first()
    actor = SimpleNamespace(id=user.id, role="system_admin")  # metering/api._actor's shape
    premises_ids = sorted(
        {
            str(row.unit.premises_id)
            for row in met.RouteMembership.objects.filter(route=src).select_related("unit")
        }
    )
    print(
        f"{src.code} '{src.name}' service={src.service.code} premises={len(premises_ids)} "
        f"members={met.RouteMembership.objects.filter(route=src).count()}\n"
    )

    # ── A · does a COLLECTED read keep its route when membership moves? ──────
    print("BEFORE THE MOVE")
    surfaces(src.id, src.code)
    dst = met.Route.objects.filter(service=src.service, status="active").exclude(pk=src.pk).first()
    surfaces(dst.id, dst.code)
    print()
    try:
        with transaction.atomic():
            # The product's own door, not a table write: this is what the wizard
            # calls, and its docstring is the claim under test.
            services.update_route(actor, dst.id, {"premises_ids": premises_ids})
            print(f"AFTER moving {src.code}'s premises onto {dst.code}")
            surfaces(src.id, src.code)
            surfaces(dst.id, dst.code)
            print(
                f"\n  meter_reads still stamped {src.code} : "
                f"{met.MeterRead.objects.filter(route_id=src.id).count()}"
            )
            raise Rollback
    except Rollback:
        print("\n(rolled back — fixture untouched)\n")
    print("AFTER ROLLBACK")
    surfaces(src.id, src.code)

    # ── B · is the STAMP still written once the projection stops being kept? ─
    print("\nB · THE FORWARD HAZARD — collection_route_id's only source")
    point = met.ServicePoint.objects.filter(route=src).select_related("unit").first()
    asset = assets_models.Asset.objects.filter(service_point=point).first()
    print(f"  asset {asset.asset_no} on unit {point.unit.label}")
    print(f"  collection_route_id WITH the point stamped  : {services.collection_route_id(asset)}")
    try:
        with transaction.atomic():
            # Exactly what a derivation design that stops writing the stored
            # projection would leave behind: membership intact, column empty.
            met.ServicePoint.objects.filter(tenant_id=tenant_id).update(route=None)
            got = services.collection_route_id(asset)
            print(f"  collection_route_id WITHOUT any point stamp : {got}")
            print(f"  -> a read collected now would be stamped route_id={got}")
            print(
                f"  route_memberships for {src.code} still present : "
                f"{met.RouteMembership.objects.filter(route=src).count()}"
            )
            raise Rollback
    except Rollback:
        print("\n(rolled back)")
