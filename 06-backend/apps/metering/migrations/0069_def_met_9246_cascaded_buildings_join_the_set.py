"""metering 0069 — buildings a cascade put on a route by UNIT rows only join the
route's PREMISES set (`DEF-MET-9250`, 2026-10-03).

⚠ THE FILE NAME SAYS 9246 AND THE DEFECT IS DEF-MET-9250: the number was
taken by DEF-TEN-9246 minutes before this was pushed, and the row was
renumbered (law 11). The name stays because it is the name databases have
APPLIED; renaming an applied migration re-runs it everywhere.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-03 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

WHAT IT REPAIRS
---------------
Since `CR-131-BRC07` (0061) the bill run scopes a route by its premises set and
its area, and ignores the per-unit `route_memberships` rows. Until 2.467.11 the
cascades (`_join_units_to_route`: an area tag, a route's area, a new unit taking
its building's routes, a premises created on a route) wrote ONLY unit rows. On a
route that holds a hand-picked building — defined by its picks, so its area no
longer fills it — every building a cascade added was on the route for every
screen counting unit rows and on NO billing cycle. Measured on a seeded Brazos
Bend: 21 of 71 routed properties, e.g. `A-10432` at `P-00053` on `RT-005`, and
the one-time bill refused every one of them *"No billing cycle"*.

THE DERIVATION IS 0061's, NARROWED
----------------------------------
A (route, building) pair is carried across from the unit rows exactly as 0061
derived them, and ONLY where the route is pick-defined or has no area:

  * a route holding at least one picked building — the case that dropped units;
  * a route with no area — a hand route, which only its set can define.

An AREA route with no pick is left exactly as it is: its area already reaches
every building it covers, and one pick would turn it pick-defined and drop the
rest of the area out of the run. The two unique constraints stay the authority
(`ignore_conflicts`): a building already on another route for the same service
is not given a second home.

It prints what it read and wrote, per 0061's lesson (hard-won law 7 habit 3): a
run that carried nothing must be told apart from one that could see nothing.

THE REVERSE removes nothing: an added pair is indistinguishable afterwards from
one a clerk picked, and deleting a clerk's pick would be the worse error.
"""

from django.db import migrations


def carry_cascaded_buildings(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django.db import connection

    if schema_editor.connection.vendor != "postgresql":
        print("  route_premises_memberships (DEF-MET-9250): sqlite — nothing to carry")
        return

    tenant_model = apps.get_model("tenancy", "Tenant")
    route_model = apps.get_model("metering", "Route")
    unit_rows = apps.get_model("metering", "RouteMembership")
    premises_rows = apps.get_model("metering", "RoutePremisesMembership")

    tenant_ids = list(tenant_model.objects.values_list("id", flat=True).order_by("id"))
    read = written = skipped_area = 0
    for tenant_id in tenant_ids:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.tenant_id = %s", [str(tenant_id)])
        picked_routes = set(
            premises_rows.objects.filter(tenant_id=tenant_id).values_list("route_id", flat=True)
        )
        areas = dict(route_model.objects.filter(tenant_id=tenant_id).values_list("id", "area_id"))
        have = set(
            premises_rows.objects.filter(tenant_id=tenant_id).values_list("route_id", "premises_id")
        )
        seen: set = set()
        rows = []
        for route_id, premises_id, service_id in (
            unit_rows.objects.filter(tenant_id=tenant_id)
            .values_list("route_id", "unit__premises_id", "service_id")
            .order_by("route_id", "unit__premises_id")
        ):
            read += 1
            key = (route_id, premises_id)
            if key in have or key in seen:
                continue
            seen.add(key)
            if route_id not in picked_routes and areas.get(route_id) is not None:
                skipped_area += 1
                continue
            rows.append(
                premises_rows(
                    tenant_id=tenant_id,
                    route_id=route_id,
                    premises_id=premises_id,
                    service_id=service_id,
                )
            )
        created = premises_rows.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)
        written += len(created)
    print(
        f"  route_premises_memberships (DEF-MET-9250): {len(tenant_ids)} tenant(s) scoped, "
        f"{read} unit rows read, {written} building(s) offered to a route's set, "
        f"{skipped_area} left to an area route's own area"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0068_cr163_connection_fee_bills"),
    ]

    operations = [
        migrations.RunPython(carry_cascaded_buildings, migrations.RunPython.noop),
    ]
