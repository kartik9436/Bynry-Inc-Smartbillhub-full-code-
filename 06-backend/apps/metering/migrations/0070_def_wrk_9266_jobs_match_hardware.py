"""metering 0070 — seeded New Connection jobs stop naming hardware Create does
not fit (`DEF-WRK-9266`, 2026-10-03).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-03 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

WHAT IT REPAIRS
---------------
The seeded work-order starters (`apps/metering/sample_data.W6_TEMPLATE_STARTERS`)
were written before two rulings took hardware off a New Connection:

  * `CR-080` (PO 2026-09-07) — a THERMAL unit fits no meter, its tonnage is on
    the unit; the starter still proposed *Meter set* (per asset, the gate);
  * `DEF-MET-9037` (PO 2026-10-02) — a SOLAR build fits no net meter; the
    starter still proposed *Net meter swap* (per asset).

Since `DEF-MET-9223` raises a per-asset job per unit, the re-walk's S2 raised
two of each — orders for hardware nobody installs. The seeder is fixed in the
same commit; this repairs a tenant that already holds the OLD seed.

WHAT IT CHANGES, AND ONLY WHERE THE ROW IS STILL THE UNTOUCHED SEED
------------------------------------------------------------------
  1. thermal *Meter set* and solar *Net meter swap* are DEACTIVATED
     (`active = false`, `BR-WRK-012`: stops new orders, leaves every order
     already raised from them readable). Never deleted.
  2. thermal *Service connection* becomes the gate — the step that now
     finishes the connection (decision log 2026-10-03) — but ONLY where this
     run retired that tenant's thermal *Meter set*, so a tenant never ends
     with two gates.

**Untouched** means every one of these holds, and a single miss leaves the row
exactly as it is (counted as `left_edited`):

  * `is_sample` true, `active` true, `version` 1, ONE published version row;
  * name, scope, sequence and gate flag equal the seed's;
  * nothing in the bundle — the header or any of Work's seven child tables —
    was written after that one publish (`templates_svc._bundle_touched_at`'s
    own test of *"the bundle changed"*).

A tenant that renamed, republished or edited a starter has made it THEIR
template; this migration never overwrites a tenant's own edits.

It prints what it read and changed, per 0061's lesson (law 7 habit 3).

THE REVERSE does nothing: a deactivated row is indistinguishable afterwards
from one a supervisor deactivated, and reactivating that would be the worse
error. `Work-013` reactivates a template in one press.
"""
from django.db import migrations

#: (service, sequence, name, scope, is_gate) — the OLD seed rows retired here.
RETIRE = (
    ("thermal_heat", 3, "Meter set", "per_asset", True),
    ("solar", 3, "Net meter swap", "per_asset", False),
)
#: The thermal row that takes the gate when its tenant's Meter set is retired.
GATE_TO = ("thermal_heat", 2, "Service connection", "per_unit", False)

#: Work's child tables of a template bundle (`templates_svc.COLLECTIONS` + details).
CHILD_MODELS = (
    "WorkOrderTemplateDetail",
    "WorkOrderTemplateSafety",
    "WorkOrderTemplateTask",
    "WorkOrderTemplateMaterial",
    "WorkOrderTemplateReading",
    "WorkOrderTemplateHelp",
    "WorkOrderTemplateAssetType",
)


def _untouched_seed(apps, tenant_id, spec):
    """The row for `spec` when it is still exactly the published seed, else
    `None` (absent) or `False` (present and edited)."""
    code, sequence, name, scope, is_gate = spec
    template = apps.get_model("metering", "WorkOrderTemplate")
    versions = apps.get_model("work", "WorkOrderTemplateVersion")
    row = template.objects.filter(
        tenant_id=tenant_id, service__code=code, sequence=sequence, is_sample=True
    ).first()
    if row is None or (not row.active and spec in RETIRE):
        # Already inactive — retired by an earlier run or by the tenant
        # themselves. Either way there is nothing for this run to do.
        return None
    if not (
        row.active
        and row.version == 1
        and row.name == name
        and row.scope == scope
        and row.is_gate is is_gate
    ):
        return False
    published = list(
        versions.objects.filter(tenant_id=tenant_id, template_id=row.id).values_list(
            "published_at", flat=True
        )
    )
    if len(published) != 1:
        return False
    newest = row.updated_at
    for model_name in CHILD_MODELS:
        child = (
            apps.get_model("work", model_name)
            .objects.filter(tenant_id=tenant_id, template_id=row.id)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        if child is not None and (newest is None or child > newest):
            newest = child
    if newest is not None and newest > published[0]:
        return False
    return row


def repair_tenant(apps, tenant_id):
    """One tenant, in the tenant context the caller has already set."""
    template = apps.get_model("metering", "WorkOrderTemplate")
    retired = gate_moved = left_edited = 0
    thermal_retired = False
    for spec in RETIRE:
        row = _untouched_seed(apps, tenant_id, spec)
        if row is None:
            continue
        if row is False:
            left_edited += 1
            continue
        # `.update()` rather than `.save()`: `auto_now` would move `updated_at`
        # and make the next publish read the bundle as changed.
        template.objects.filter(pk=row.pk).update(active=False)
        retired += 1
        thermal_retired = thermal_retired or spec[0] == "thermal_heat"
    if thermal_retired:
        row = _untouched_seed(apps, tenant_id, GATE_TO)
        if row:
            template.objects.filter(pk=row.pk).update(is_gate=True)
            gate_moved += 1
        elif row is False:
            left_edited += 1
    return {"retired": retired, "gate_moved": gate_moved, "left_edited": left_edited}


def repair(apps, schema_editor):  # type: ignore[no-untyped-def]
    tenant_model = apps.get_model("tenancy", "Tenant")
    tenant_ids = list(tenant_model.objects.values_list("id", flat=True).order_by("id"))
    postgres = schema_editor.connection.vendor == "postgresql"
    totals = {"retired": 0, "gate_moved": 0, "left_edited": 0}
    for tenant_id in tenant_ids:
        if postgres:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.tenant_id = %s", [str(tenant_id)])
        for key, value in repair_tenant(apps, tenant_id).items():
            totals[key] += value
    print(
        f"  work_order_templates (DEF-WRK-9266): {len(tenant_ids)} tenant(s) read, "
        f"{totals['retired']} seeded job(s) for unfitted hardware deactivated, "
        f"{totals['gate_moved']} thermal gate(s) moved to Service connection, "
        f"{totals['left_edited']} edited by the tenant and left alone"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0069_def_met_9246_cascaded_buildings_join_the_set"),
        ("work", "0027_br_wrk_018_seed_default_priorities"),
    ]

    operations = [
        migrations.RunPython(repair, migrations.RunPython.noop),
    ]
