# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — P0.1 (seed priorities on the
#           existing SAMPLE orders, `DEF-WRK-9571`) and the data half of P1.31
#           (a finished job reads Complete on the dispatch axis, `DEF-WRK-9526`)
# Rules:    BR-WRK-018 (a priority carries the promise; due_at = raise + SLA) ·
#           BR-WRK-023 (seven dispatch tokens, `complete` among them) · PO
#           answer (1) of 2026-10-04 (an undated job is measured against the
#           Normal priority) · BR-TEN-057 (sample rows only for P0.1)
# Tests:    06-backend/tests/test_cr168_srv1_migrations_pg.py
# ───────────────────────────────────────────────────────
"""metering 0072 — sample jobs get a priority; finished jobs read Complete.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT IT CHANGES
---------------
**1 · P0.1 (`DEF-WRK-9571`) — ONLY on `is_sample` rows with no priority.** Each
takes its job type's default priority, else its heading's (`_resolve_priority`'s
walk, one level), else the tenant's `NORMAL` — PO answer (1): *"a job with no due
date and no priority is measured against … the Normal priority's hours"*. Where
`due_at` is NULL it is stamped `created_at + sla_hours`, the raise-time rule of
`BR-WRK-018`, so the demo's *Due* column says what it would have said had the
priority existed at the raise. **A utility's own order is never touched** — an
order a person raised with no priority is THEIR fact, and inventing a promise
for it is what `_resolve_priority` refuses to do.

**2 · P1.31 (`DEF-WRK-9526`) — EVERY tenant's finished orders.** `state =
'completed'` and `dispatch_state` not `complete` → `complete`, EXCEPT where the
order is `on_hold` or `cancelled`: those are a person's deliberate act and are
left exactly as they are (the `_refresh_cache` posture). On the demo this is 22
`queued` and 1 `on_site` jobs that were finished days ago.

Both write through the ORM under each tenant's own `app.tenant_id`
(`work_orders` and `work_priorities` carry FORCE), and the GUC is restored to its
arrival state — `work/0027`'s shape. It prints what it read and changed.

THE REVERSE IS A NO-OP, STATED: a corrected dispatch token and a stamped sample
priority are indistinguishable afterwards from ones a person set, and undoing a
person's act to satisfy a rollback is the worse error (§8 *Rollback*).
"""

from datetime import timedelta

from django.db import migrations

DONE = "complete"
LEFT_ALONE = ("on_hold", "cancelled", "complete")


def _priority_for(order, priorities_by_id, normal):
    type_ref = order.type_ref
    if type_ref is not None:
        if type_ref.default_priority_id:
            return priorities_by_id.get(type_ref.default_priority_id)
        parent = type_ref.parent
        if parent is not None and parent.default_priority_id:
            return priorities_by_id.get(parent.default_priority_id)
    return normal


def _apply_tenant(apps_registry, tenant_id):
    WorkOrder = apps_registry.get_model("metering", "WorkOrder")
    WorkPriority = apps_registry.get_model("work", "WorkPriority")
    priorities_by_id = {p.id: p for p in WorkPriority.objects.filter(tenant_id=tenant_id)}
    normal = next(
        (p for p in priorities_by_id.values() if (p.code or "").upper() == "NORMAL"), None
    )
    seeded = dated = 0
    for order in WorkOrder.objects.filter(
        tenant_id=tenant_id, is_sample=True, priority__isnull=True
    ).select_related("type_ref__parent"):
        priority = _priority_for(order, priorities_by_id, normal)
        if priority is None:
            continue
        order.priority_id = priority.id
        fields = ["priority"]
        if order.due_at is None and priority.sla_hours:
            order.due_at = order.created_at + timedelta(hours=int(priority.sla_hours))
            fields.append("due_at")
            dated += 1
        order.save(update_fields=fields)
        seeded += 1
    completed = (
        WorkOrder.objects.filter(tenant_id=tenant_id, state="completed")
        .exclude(dispatch_state__in=LEFT_ALONE)
        .update(dispatch_state=DONE)
    )
    return seeded, dated, completed


def apply(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"
    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]
    totals = [0, 0, 0]
    tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            for index, count in enumerate(_apply_tenant(apps_registry, tenant_id)):
                totals[index] += count
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])
    if tenants:
        print(
            f"cr-168 work orders: {tenants} tenant(s) — {totals[0]} sample order(s) given a "
            f"priority ({totals[1]} dated from it), {totals[2]} finished order(s) moved to "
            "Complete on the dispatch axis"
        )


def undo(apps_registry, schema_editor):
    """A NO-OP, and stated rather than silent — see the module docstring."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0071_cr168_acceptance_and_hold_columns"),
        ("work", "0027_br_wrk_018_seed_default_priorities"),
        ("tenancy", "0058_storm_water_flat_size"),
    ]

    operations = [migrations.RunPython(apply, undo)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (row metering/0072) · DEF-WRK-9571 · DEF-WRK-9526
# generated: 2026-10-04 by CR-168 round 2 lane SRV-1
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: migrate up → down → up on PostgreSQL 16 against the seeded demo
# exceptions: the reverse is a stated no-op (a corrected token is indistinguishable)
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
