"""CR-168-BRC10 round 5, lane PERFORMANCE — put the demo into the states the
three boards are photographed in. A SCRATCH database only, never a real tenant.

    cd 06-backend
    export DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
           DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    python manage.py shell < ../10-scripts/cr168_perf_walk_prep.py

What it does, through the product's own services wherever one exists:
  * the at-risk window to 72 h (`workforce.set_default_target`, the setting
    `GET/POST /work/settings/sla` carries);
  * three open jobs PAST their promise and two due within hours — `due_at`
    written directly, because the product has no act that moves a promise
    into the past (a demo needs a breach today, not in three days);
  * two jobs given to technicians for today through the bulk assign the
    schedule board uses (`dispatch.bulk_act`), one of them to a technician
    then set OFF TODAY, so the board has an over-assigned row to show.

It prints what it did, by order number and name — never an id.
"""
from datetime import timedelta

from django.utils import timezone

from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant
from apps.work import dispatch, workforce
from apps.work import models as work_models
from core import tenancy as core_tenancy

tenant = Tenant.objects.get(subdomain="brazosbend")
now = timezone.now()
with core_tenancy.tenant_context(tenant.id):
    from apps.identity import models as identity_models

    dana = identity_models.User.objects.get(email="dana@brazosbendutilities.com")
    actor = type("Actor", (), {"id": dana.id, "role": "system_admin"})()
    print("window:", workforce.set_default_target(actor, {"at_risk_window_hours": 72})["at_risk_window_hours"])
    open_rows = list(
        work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, state__in=("planned", "in_progress", "blocked"))
        .exclude(dispatch_state__in=("on_hold", "cancelled"))
        .order_by("order_no")
    )
    for row, hours in zip(open_rows[:5], (-30, -6, -2, 3, 9)):
        work_tables.WorkOrder.objects.filter(pk=row.pk).update(due_at=now + timedelta(hours=hours))
        print(f"{row.order_no}: promise moved to now {hours:+d} h")
    techs = list(work_models.Technician.objects.filter(tenant_id=tenant.id).select_related("user").order_by("user__full_name"))
    unassigned = [r for r in open_rows[5:] if r.assignee_technician_id is None and r.assignee_crew_id is None]
    day = timezone.localtime(now).date().isoformat()
    for tech, row in zip(techs[:2], unassigned[:2]):
        answer = dispatch.bulk_act(
            actor,
            {"act": "assign", "ids": [str(row.id)], "technician_id": str(tech.id),
             "window_start": f"{day}T08:00:00", "window_end": f"{day}T12:00:00"},
        )
        print(f"{row.order_no} -> {tech.user.full_name}: done {answer['done']}, failed {answer['failed']}")
    if len(techs) > 1:
        off = techs[1]
        work_models.Technician.objects.filter(pk=off.pk).update(status=work_models.Technician.STATUS_OFF_TODAY)
        print(f"{off.user.full_name}: off today")
