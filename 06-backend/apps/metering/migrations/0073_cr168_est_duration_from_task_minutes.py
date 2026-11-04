# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — P3.47 (a job's estimate is its
#           template's task minutes; *"WO-0043 carries 38 min, and Avg vs
#           estimate has a value"*)
# Rules:    BR-WRK-008 (the job's task rows are its own copy) · CLAUDE.md 🔒
#           migration ordering · hard rule 1 (per tenant, under app.tenant_id)
# Tests:    06-backend/tests/test_cr168_srv3_templates.py (the raise half);
#           this data task is run up → down → up on PostgreSQL 16
# ───────────────────────────────────────────────────────
"""metering 0073 — a job with no estimate takes the sum of its OWN task minutes.

From `2.503.0` the raise stamps `est_duration` from the template's tasks
(`connections._resolve_est_duration`). Jobs raised before it carry none —
measured, 0 of 40 on the demo — so *against estimate* could not be counted.
For every order with `est_duration IS NULL` and at least one copied task row
(`work_order_tasks`, the job's own copy, never the template as it reads today),
this writes the sum of those rows' minutes when it is above zero. An order with
no task rows, or whose tasks sum to 0, is left alone: zero is not an estimate.

Per tenant under `app.tenant_id` (RLS `FORCE`), the `metering/0072` shape. It
prints what it read and changed. **The reverse is a NO-OP, stated:** a filled
estimate is indistinguishable afterwards from one the raise wrote, so undoing it
would also clear estimates nobody back-filled.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-04 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from datetime import timedelta

from django.db import migrations
from django.db.models import Sum


def _apply_tenant(apps_registry, tenant_id):
    WorkOrder = apps_registry.get_model("metering", "WorkOrder")
    WorkOrderTask = apps_registry.get_model("work", "WorkOrderTask")
    read = filled = 0
    minutes_by_order = {
        row["work_order_id"]: row["total"]
        for row in WorkOrderTask.objects.filter(tenant_id=tenant_id)
        .values("work_order_id")
        .annotate(total=Sum("est_minutes"))
    }
    for order in WorkOrder.objects.filter(tenant_id=tenant_id, est_duration__isnull=True).only(
        "id", "est_duration"
    ):
        read += 1
        minutes = minutes_by_order.get(order.id)
        if minutes:
            order.est_duration = timedelta(minutes=int(minutes))
            order.save(update_fields=["est_duration"])
            filled += 1
    return read, filled


def apply(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"
    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]
    read = filled = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            one_read, one_filled = _apply_tenant(apps_registry, tenant_id)
            read += one_read
            filled += one_filled
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])
    if tenants:
        print(
            f"cr-168 P3.47: {tenants} tenant(s) — {read} order(s) with no estimate read, "
            f"{filled} given the sum of their own task minutes"
        )


def undo(apps_registry, schema_editor):
    """A NO-OP, and stated rather than silent — see the module docstring."""
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0072_cr168_priorities_and_complete_dispatch"),
        ("work", "0034_cr168_task_instruction_copy_and_help_link"),
    ]

    operations = [migrations.RunPython(apply, undo)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (POST /work-orders: est_duration = the template's task minutes) · §16
# generated: 2026-10-04 by CR-168 round 4 lane SRV-3
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
