# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13, lane S-ORDER — shared fixtures for the
#           `test_cr187_order_*` files. No tests of its own.
# ───────────────────────────────────────────────────────
"""A job a technician holds, closed the way the product closes one, and a
second technician — built through the product's own doors."""

from __future__ import annotations

from types import SimpleNamespace

from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist, mobile
from apps.work import models as work_models
from core.permissions import FIELD_TECHNICIAN

from tests.test_us_met_helpers import field_actor, take_required_photos
from tests.test_us_wrk_032_copies import (
    SEVEN_TASKS,
    THREE_HELP,
    THREE_READINGS,
    THREE_SAFETY,
    _raise,
)

FIX = {
    "lat": "30.261200",
    "lng": "-97.743100",
    "accuracy_m": "4.0",
    "fix_at": "2026-03-15T16:05:00Z",
}

DEFAULT_TEMPLATE = "Meter exchange — residential"


def _parts(tenant):
    """`test_us_wrk_032_copies._parts`, but get-or-create: several templates in
    one test share the tenant's part register (`uq_parts_tenant_part_no_ci`)."""
    from decimal import Decimal

    rows = []
    for no, name, uom, cost in (
        ("MTR-E1P", "Electric meter, single phase", "each", "92.4000"),
        ("SEAL-R", "Meter seal, red", "each", "0.2200"),
        ("TAIL-25", "Meter tail, 25mm", "metre", "3.1000"),
    ):
        part = work_models.Part.objects.filter(tenant_id=tenant.id, part_no=no).first()
        if part is None:
            part = work_models.Part.objects.create(
                tenant_id=tenant.id,
                part_no=no,
                name=name,
                unit_of_measure=uom,
                unit_cost=Decimal(cost),
            )
        rows.append(part)
    return rows


def template(actor, tenant, name=DEFAULT_TEMPLATE):
    """ONE published template per name per tenant, at v2 — reused when asked
    again (`test_us_wrk_032_copies._published_template`'s six collections)."""
    from apps.work import templates_svc

    existing = (
        work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant.id, name=name)
        .values_list("id", flat=True)
        .first()
    )
    if existing is not None:
        return existing
    tid = templates_svc.create_draft(actor, {"name": name, "service": "electric"})["id"]
    templates_svc.replace_collection(actor, tid, "tasks", SEVEN_TASKS)
    templates_svc.replace_collection(actor, tid, "readings", THREE_READINGS)
    templates_svc.replace_collection(actor, tid, "safety", THREE_SAFETY)
    templates_svc.replace_collection(actor, tid, "help", THREE_HELP)
    templates_svc.replace_collection(
        actor,
        tid,
        "materials",
        [{"part_id": str(p.id), "planned_qty": q} for p, q in zip(_parts(tenant), (1, 2, 3))],
    )
    templates_svc.replace_collection(actor, tid, "details", {"show_asset_card": False})
    templates_svc.publish(actor, tid)
    templates_svc.replace_collection(actor, tid, "help", THREE_HELP)
    assert templates_svc.publish(actor, tid)["version"] == 2
    return tid


def job(actor, tenant, **extra):
    """A raised job held by the tenant's field technician, accepted by them.
    Returns `(order_id, technician_actor)`."""
    tid = template(actor, tenant)
    oid = _raise(actor, tenant, tid, **extra)["id"]
    tech = field_actor(oid, actor)
    mobile.accept_job(tech, oid)
    return oid, tech


def person(tenant, email, name, *, role_label="Field technician", crew=None):
    """Another technician of `tenant`: `(Technician, actor)`."""
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(tenant_id=tenant.id, email=email).first()
    if user is None:
        user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    technician, _ = work_models.Technician.objects.get_or_create(
        tenant_id=tenant.id, user=user, defaults={"role_label": role_label, "crew": crew}
    )
    return technician, SimpleNamespace(id=user.id, role=FIELD_TECHNICIAN)


def tick_safety(tech, oid):
    for row in work_models.WorkOrderSafety.objects.filter(work_order_id=oid):
        checklist.tick_safety(tech, oid, row.id)


def tick_tasks(tech, oid, how_many):
    rows = list(work_models.WorkOrderTask.objects.filter(work_order_id=oid).order_by("seq"))
    for row in rows[:how_many]:
        checklist.tick_task(tech, oid, row.id)
    return rows


def close(tech, oid, outcome="passed", *, field_data=None, tasks=None, completed_at=None):
    """Close as the field: safety ticked, `tasks` of the steps ticked (all when
    None), required photographs taken, then `submit_field_result`."""
    tick_safety(tech, oid)
    total = work_models.WorkOrderTask.objects.filter(work_order_id=oid).count()
    tick_tasks(tech, oid, total if tasks is None else tasks)
    take_required_photos(tech, oid)
    return w6.submit_field_result(
        tech,
        oid,
        outcome=outcome,
        field_data=field_data,
        completed_at=completed_at or timezone.now(),
    )


def order(oid):
    return work_tables.WorkOrder.objects.get(pk=oid)
