"""`CR-131-BRC07` §0 — the two scale figures, MEASURED rather than extrapolated.

The CR's symptom table carries two estimates read off the code: *"one `unit_id`
query parameter per unit — 726 × ~45 chars ≈ a 33,000-character URL"* and
*"~1,450 sequential round trips"*. This CALLS `selectors.route_meter_picker`
with the query log captured and counts what it really costs per unit, then
scales. **Both estimates turned out LOW.**

⚠ **IT SCALES FROM A REAL MEASUREMENT, IT DOES NOT SIMULATE 726 UNITS.** The
per-unit cost is what is measured; the 726-unit figure is arithmetic on it and
is labelled as such. A script that claimed to have run 726 units without seeding
them would be the false-confidence this repo keeps filing defects about.

WHAT WOULD MAKE THIS PASS WRONGLY: counting the queries of a warmed cache or of
a route whose units carry no assets — `assets_on_unit` is the per-unit hop, so a
route with no meters would under-count it. Print `meters returned` beside the
query count so a reader can see the loop actually did its work.

HOW TO RUN IT
-------------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://…/sbh_clone_<label> \
      python3 manage.py shell < ../10-scripts/cr131_scale_measure.py

Measured on `brazosbend`, seeded clone of pinned tip `cb2757596`, 2026-09-22:

    route_meter_picker on 9 units -> 46 queries (5.1 per unit); 18 meters returned;
      the selector takes no page argument
    URL the front end builds for 9 units: 471 chars (52 per unit)
      at 726 units -> 37,994 chars against a 4-8 KB server limit
      at 726 units -> 3,711 sequential round trips for step 3
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.metering import models as met
from apps.metering import selectors
from apps.tenancy import models as ten
from core import tenancy

TENANT = "brazosbend"
ROUTE = "RT-009"
#: The property size the PO hit it on, from the CR's §5 acceptance line.
TARGET_UNITS = 726

tenant_id = str(ten.Tenant.objects.get(subdomain=TENANT).id)
with tenancy.tenant_context(tenant_id):
    route = met.Route.objects.get(code=ROUTE)
    unit_ids = [str(row.unit_id) for row in met.RouteMembership.objects.filter(route=route)]
    n = len(unit_ids)
    with CaptureQueriesContext(connection) as ctx:
        picked = selectors.route_meter_picker(unit_ids, str(route.id))
    queries = len(ctx.captured_queries)
    print(
        f"route_meter_picker on {n} units -> {queries} queries "
        f"({queries / n:.1f} per unit); {picked['total']} meters returned; "
        f"the selector takes no page argument"
    )
    url = (
        "/routes/meter-picker?"
        + "&".join(f"unit_id={unit_id}" for unit_id in unit_ids)
        + f"&route_id={route.id}"
    )
    print(f"URL the front end builds for {n} units: {len(url)} chars ({len(url) / n:.0f} per unit)")
    print(
        f"  at {TARGET_UNITS} units -> {len(url) / n * TARGET_UNITS:,.0f} chars "
        f"against a 4-8 KB server limit"
    )
    print(
        f"  at {TARGET_UNITS} units -> {queries / n * TARGET_UNITS:,.0f} "
        f"sequential round trips for step 3"
    )
