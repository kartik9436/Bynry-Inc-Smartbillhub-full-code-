"""CR-168-BRC10 §30, lane BOARDS — put the demo into the states the walk
photographs. A SCRATCH database only, never a real tenant.

    cd 06-backend
    export DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
           DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    python manage.py shell < ../10-scripts/cr168_boards_walk_prep.py

What it does, through the product's own services wherever one exists:
  * the at-risk window to 72 h (`workforce.set_default_target`), so the At
    risk tab has rows;
  * D. Ortiz's daily job limit set to 7 (`workforce.set_daily_job_limit`), so
    the walk can EDIT it back to the PO's 6 on his page;
  * SEVEN jobs given to D. Ortiz for TOMORROW through the bulk assign the
    Schedule board itself uses (`dispatch.bulk_act`) — raising more through
    metering's own raise when the demo has too few open unassigned jobs;
  * one of the three aged sample meters (`AST-04413`) INSTALLED on a unit
    through an open `asset_assignments` row (written directly: Work may not
    write assets, and this is a demo fixture, not a product act), so the
    Asset age rule has one installed meter and two on the shelf; then the
    rule's sweep is run once.

It prints what it did, by order number and name — never an id.
"""
from datetime import date, timedelta

from django.utils import timezone

from apps.assets import models as assets_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.tenancy.models import Tenant
from apps.work import dispatch, rules, workforce
from apps.work import models as work_models
from apps.work.rules_models import WorkOrderRule
from core import tenancy as core_tenancy

tenant = Tenant.objects.get(subdomain="brazosbend")
now = timezone.now()
day = (timezone.localtime(now).date() + timedelta(days=1)).isoformat()
with core_tenancy.tenant_context(tenant.id):
    from apps.identity import models as identity_models

    dana = identity_models.User.objects.get(email="dana@brazosbendutilities.com")
    actor = type("Actor", (), {"id": dana.id, "role": "system_admin"})()
    print("window:", workforce.set_default_target(actor, {"at_risk_window_hours": 72})["at_risk_window_hours"])

    ortiz = work_models.Technician.objects.select_related("user").get(
        tenant_id=tenant.id, user__full_name="D. Ortiz"
    )
    workforce.set_daily_job_limit(actor, ortiz.id, 7)
    print("D. Ortiz limit:", work_models.Technician.objects.get(pk=ortiz.pk).daily_job_limit)

    open_rows = list(
        work_tables.WorkOrder.objects.filter(
            tenant_id=tenant.id,
            state__in=("planned", "in_progress", "blocked"),
            assignee_technician_id__isnull=True,
            assignee_crew_id__isnull=True,
        )
        .exclude(dispatch_state__in=("on_hold", "cancelled"))
        .order_by("order_no")
    )
    premises = metering_models.Premises.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    while len(open_rows) < 8:
        raised = w6.create_work_order(
            actor, None, {"type": "Leak investigation", "premises_id": str(premises.id)}
        )
        open_rows.append(work_tables.WorkOrder.objects.get(pk=raised["id"]))
        print("raised", raised.get("order_no"))
    ids = [str(row.id) for row in open_rows[:7]]
    answer = dispatch.bulk_act(
        actor,
        {"act": "assign", "ids": ids, "technician_id": str(ortiz.id),
         "window_start": f"{day}T08:00:00", "window_end": f"{day}T12:00:00"},
    )
    print(f"7 jobs on {day} -> D. Ortiz: done {answer['done']}, failed {answer['failed']}")

    installed = assets_models.Asset.objects.get(tenant_id=tenant.id, asset_no="AST-04413")
    unit = metering_models.Unit.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    if not assets_models.AssetAssignment.objects.filter(asset_id=installed.id, to_date__isnull=True).exists():
        assets_models.AssetAssignment.objects.create(
            tenant_id=tenant.id, asset_id=installed.id, unit_id=unit.id, from_date=date(2024, 1, 1)
        )
    print(f"AST-04413 installed on {unit.label}; AST-04412 and AST-04414 stay on the shelf")

    rule = WorkOrderRule.objects.filter(tenant_id=tenant.id, name="Asset age rule").first()
    if rule is not None:
        if not rule.enabled:
            rule.enabled = True
            rule.save(update_fields=["enabled", "updated_at"])
        report = rules.sweep(actor, rule_ids=[str(rule.id)])["rules"][0]
        raised = list(
            work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, rule_id=rule.id)
            .select_related("asset")
            .values_list("order_no", "asset__asset_no")
        )
        print(f"rule {rule.name}: raised {report['raised']}; its jobs {raised}")
