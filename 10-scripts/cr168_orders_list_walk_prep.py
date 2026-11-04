#!/usr/bin/env python3
"""CR-168-BRC10 round 2, lane ORDERS-LIST — fill the Approvals queue for the after-walk.

A fresh ``seed_demo`` + ``load_sample_data --tenant brazosbend`` leaves the queue
EMPTY (every finished demo job is already accepted), so images 21–23 cannot be
photographed without field work to accept. This closes three demo jobs AS THEIR
TECHNICIAN, the way the field app does (ruling 18 — the office never completes
a job), through metering's own ``submit_field_result``:

  * WO-0037 (D. Ortiz's, has a build) — Passed
  * WO-0038 (R. Patel's, en route, has a build) — Passed
  * WO-0021 — assigned to a technician first, then Partially done

Run from ``06-backend`` with the walk's database:

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_wlist \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python manage.py shell < ../10-scripts/cr168_orders_list_walk_prep.py

It prints what it changed. Writes nothing to any other tenant.
"""
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant
from apps.work import checklist as work_checklist
from apps.work import dispatch
from apps.work import models as work_models
from apps.identity import models as identity_models
from core import tenancy as core_tenancy
import base64
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.work import evidence
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

tenant = Tenant.objects.get(subdomain="brazosbend")
with core_tenancy.tenant_context(tenant.id):
    dana = identity_models.User.objects.filter(tenant_id=tenant.id, email__startswith="dana").first()
    for order_no, outcome in (("WO-0037", "passed"), ("WO-0038", "passed"), ("WO-0021", "partially_done")):
        order = work_tables.WorkOrder.objects.get(order_no=order_no)
        if order.state == "completed":
            print(order_no, "already completed — left alone")
            continue
        if order.assignee_technician_id is None:
            tech = work_models.Technician.objects.filter(tenant_id=tenant.id).order_by("id").first()
            dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})
            order.refresh_from_db()
        tech = work_models.Technician.objects.get(pk=order.assignee_technician_id)
        # The technician ticks the safety rows first, as on the phone — the
        # server refuses a close with a mandatory safety row open (BR-WRK-037).
        for row in work_checklist.checklist(order.id)["safety"]:
            if row["ticked_at"] is None:
                work_checklist.tick_safety(tech.user, order.id, row["id"])
        # Round 7 (WALK-A): since the photo guard (P1.33) a close with a required
        # photograph missing is refused, so the technician attaches one first,
        # as on the phone.
        for task in work_models.WorkOrderTask.objects.filter(work_order_id=order.id).order_by("seq"):
            if task.photo_required:
                evidence.record_attachment(tech.user, order.id, {
                    "idempotency_key": f"r7-task-{task.seq}-{order.id}", "task_id": str(task.id),
                    "content_type": "image/png", "display_name": f"task-{task.seq}.png",
                }, SimpleUploadedFile(f"task-{task.seq}.png", PNG, content_type="image/png"))
        for reading in work_models.WorkOrderReading.objects.filter(work_order_id=order.id).order_by("seq"):
            if reading.photo_required:
                evidence.record_attachment(tech.user, order.id, {
                    "idempotency_key": f"r7-reading-{reading.seq}-{order.id}", "reading_id": str(reading.id),
                    "content_type": "image/png", "display_name": f"reading-{reading.seq}.png",
                }, SimpleUploadedFile(f"reading-{reading.seq}.png", PNG, content_type="image/png"))
        w6.submit_field_result(tech.user, order.id, field_data={"walk": "CR-168 ORDERS-LIST"}, outcome=outcome)
        print(order_no, "closed by", tech.user.full_name, "as", outcome)
