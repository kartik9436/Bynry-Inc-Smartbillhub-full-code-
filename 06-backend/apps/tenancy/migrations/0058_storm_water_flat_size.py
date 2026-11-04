"""tenancy 0058 — storm water's seeded size "Flat" = 2 ERU reaches an existing
tenant whose storm-water list is still the untouched seed (PO ruling
2026-10-03, decision log, option A).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-03 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

THE RULING
----------
PO verbatim: *"A Keep charging per unit, and add a size for a single flat, e.g.
"Flat" = 2 ERU"*. Storm water is charged PER UNIT; the five seeded sizes name
kinds of PROPERTY, so a clerk sizing each of three flats could only pick
*Apartment building* — 3 × 6 ERU × $4.50 = **$81.00**, the building's hard
surface charged three times — where *Flat* gives 3 × 2 ERU × $4.50 = **$27.00**.
The row is a SEEDED DEFAULT a utility edits on Settings, not signed law. Its
capacity (2 ERU) lives in `apps/tenancy/service_size_classes.py`, never on the
row, exactly like the five beside it.

WHY A MIGRATION AND NOT THE SWEEP
---------------------------------
`service_size_classes` is a DISCRETIONARY list (it is not in
`STRUCTURAL_REFERENCE_LISTS`), so the post-migrate reference sweep DEFERS it and
a fixture bump alone reaches only tenants provisioned from now on.

ONLY WHERE THE LIST IS STILL THE UNTOUCHED SEED
-----------------------------------------------
A tenant receives the row only when its storm-water rows are EXACTLY the five
seeded ones — same codes, same names, all `is_system`, all active, nothing
added — and it holds no `SW-FLAT` already (case-insensitive, the table's own
key). A utility that renamed, deactivated or added a storm-water size owns its
list, and this migration never writes into a utility's own list. It prints what
it read, added and left (law 7 habit 3).

THE REVERSE removes nothing: an added row is indistinguishable afterwards from
one the utility kept on purpose, and it may be in use on a unit.
"""
from django.db import migrations
from django.db.models.functions import Lower

SEEDED = {
    "SW-SF": "Single-family home",
    "SW-DUP": "Two-unit home",
    "SW-APT": "Apartment building",
    "SW-COM-S": "Small commercial",
    "SW-COM-L": "Large commercial",
}
FLAT_CODE = "SW-FLAT"
FLAT_NAME = "Flat"


def add_flat_for_tenant(apps, tenant_id):
    """One tenant, in the tenant context the caller has already set.
    Returns `added`, `left_edited` or `skipped` (no storm-water list at all,
    or Flat already held)."""
    size = apps.get_model("tenancy", "MeterSizeClass")
    service = apps.get_model("tenancy", "Service").objects.filter(code="storm_water").first()
    if service is None:
        return "skipped"
    if size.objects.filter(tenant_id=tenant_id).annotate(lc=Lower("code")).filter(
        lc=FLAT_CODE.lower()
    ).exists():
        return "skipped"
    rows = list(
        size.objects.filter(tenant_id=tenant_id, service_id=service.id).values_list(
            "code", "name", "is_system", "active"
        )
    )
    if not rows:
        return "skipped"
    if sorted(rows) != sorted((code, name, True, True) for code, name in SEEDED.items()):
        return "left_edited"
    size.objects.create(
        tenant_id=tenant_id,
        code=FLAT_CODE,
        name=FLAT_NAME,
        service_id=service.id,
        is_system=True,
        active=True,
    )
    return "added"


def add_flat(apps, schema_editor):  # type: ignore[no-untyped-def]
    tenant_model = apps.get_model("tenancy", "Tenant")
    tenant_ids = list(tenant_model.objects.values_list("id", flat=True).order_by("id"))
    postgres = schema_editor.connection.vendor == "postgresql"
    totals = {"added": 0, "left_edited": 0, "skipped": 0}
    for tenant_id in tenant_ids:
        if postgres:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.tenant_id = %s", [str(tenant_id)])
        totals[add_flat_for_tenant(apps, tenant_id)] += 1
    print(
        f"  meter_size_classes (storm water Flat, PO 2026-10-03): {len(tenant_ids)} tenant(s) read, "
        f"{totals['added']} given 'Flat' (2 ERU), {totals['left_edited']} with their own "
        f"storm-water list left alone, {totals['skipped']} with no list or Flat already"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0057_cr161_w4_custom_field_entities"),
    ]

    operations = [
        migrations.RunPython(add_flat, migrations.RunPython.noop),
    ]
