# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-10220 (PO 2026-10-17, decision log "SOLAR/BATTERY BILL THE
#           SUM OF INSTALLED kW; A TENANT-ADDED SIZE CARRIES ITS OWN CAPACITY")
# Rules:    BR-TEN-171 (the ratified capacities) · BR-TEN-071 (insert-if-absent;
#           a tenant's own value is never overwritten) · CLAUDE.md hard rule 1
#           (RLS on `meter_size_classes` untouched and honoured, one tenant at a
#           time) · hard rule 3 (a capacity is in its service's unit)
# Tests:    06-backend/tests/test_def_rat_10220_size_class_capacity.py
# ───────────────────────────────────────────────────────
"""tenancy 0064 — **a size class carries its own capacity, and the built-in
ones are given theirs.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. Ledger row: `12-governance/09-human-review-ledger.md`,
*"A size class carries its own capacity"*.

WHY. The PO added `SOL-P47.84 · Solar Panal 47.84` in Settings and the bill
could not know it was 47.84 kW: the row had a code and a name and nothing else.
PO, verbatim: *"do not hard code anything - we need to stay with logi and make
logical corrections; it should able to handle dyanmic capacities and calcualte
based on logic"*. So the number lives ON THE ROW, one column for every size.

WHAT IT WRITES. (1) `capacity NUMERIC(18,4) NULL`. (2) For every tenant, every
row whose capacity is NULL, whose service tag is set, and whose code is one of
the platform's ratified capacity sizes FOR THAT SERVICE gets the ratified
figure — so a built-in size reads from the same column as a tenant-added one.
A row that already carries a value is never touched (BR-TEN-071).

FROZEN VALUES, NOT READ FROM THE LADDER — `tenancy/0048`'s reasoning: a
migration that consulted the live module would silently change meaning the
next time the module moves. These are `service_size_classes`' capacities on
2026-10-17, copied. The live seed reads the ladder itself.

RLS. `meter_size_classes` is ENABLE + FORCE, so the tenant is set transaction-
locally before each tenant's write (`tenancy/0063`'s loop). SQLite has neither.

REVERSE. Drops the column; the ladder re-seeds the built-in figures.
"""

from decimal import Decimal

from django.db import migrations, models

#: (service code, size-class code) -> capacity, in that service's own unit.
RATIFIED_CAPACITIES = {
    **{("solar", f"SOL-P{n}"): Decimal(n) for n in range(1, 11)},
    **{("battery", f"BAT-{n}"): Decimal(n) for n in (5, 10, 15, 20, 25, 30)},
    **{("broadband", f"BB-{n}"): Decimal(n) for n in (100, 500, 1000)},
    **{("thermal_heat", f"TH-T{n}"): Decimal(n) for n in (5, 10, 25, 50, 100, 200, 400, 800)},
    ("storm_water", "SW-SF"): Decimal(1),
    ("storm_water", "SW-DUP"): Decimal(2),
    ("storm_water", "SW-FLAT"): Decimal(2),
    ("storm_water", "SW-APT"): Decimal(6),
    ("storm_water", "SW-COM-S"): Decimal(4),
    ("storm_water", "SW-COM-L"): Decimal(10),
}


def _tenant_ids(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT id FROM tenants ORDER BY id")
        return [row[0] for row in cursor.fetchall()]


def _scope(schema_editor, tenant_id) -> None:
    """SET LOCAL the tenant (CLAUDE.md hard rule 1) — discarded at commit."""
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])


def forwards(apps, schema_editor):
    MeterSizeClass = apps.get_model("tenancy", "MeterSizeClass")
    wanted = {(svc, code.casefold()): cap for (svc, code), cap in RATIFIED_CAPACITIES.items()}
    for tenant_id in _tenant_ids(schema_editor):
        _scope(schema_editor, tenant_id)
        rows = MeterSizeClass.objects.filter(
            tenant_id=tenant_id, capacity__isnull=True, service__isnull=False
        ).select_related("service")
        for row in rows:
            capacity = wanted.get((row.service.code, row.code.strip().casefold()))
            if capacity is not None:
                MeterSizeClass.objects.filter(pk=row.pk).update(
                    capacity=capacity.quantize(Decimal("0.0001"))
                )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0063_def_bil_10147_correction_case_series")]

    operations = [
        migrations.AddField(
            model_name="metersizeclass",
            name="capacity",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
