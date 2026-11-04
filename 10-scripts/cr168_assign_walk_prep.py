"""CR-168-BRC10 round 3, lane ASSIGN — put image 12's state into the demo for the after-walk.

A fresh ``seed_demo`` + ``load_sample_data --tenant brazosbend`` has NO unassigned
job whose template names a skill (every skilled job is already held), so the
advice beside each name has nothing to say on an *Assign* page. This takes
WO-0027 (*Site inspection & mark-out*, needs **Water I**, D. Ortiz's) off D.
Ortiz through the dispatcher's own act — ``dispatch.record_act`` with
``unassign``, the same write the edit page makes — so it is a job nobody holds
that needs a skill. On the demo that gives the four advice cases the proof is
about, with no data invented:

  * R. Patel, D. Ortiz — hold Water I
  * J. Okoro — holds Water I, and his certificate lapsed on 2026-09-22 (seeded)
  * M. Chen — does NOT hold Water I (Electric I, Meter I, Reads)

Run from ``06-backend`` with the walk's database:

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_wassign \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python manage.py shell < ../10-scripts/cr168_assign_walk_prep.py

Idempotent: a job already unassigned is left alone. Writes nothing to any other tenant.
"""
from apps.identity import models as identity_models
from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant
from apps.work import dispatch
from core import tenancy as core_tenancy

tenant = Tenant.objects.get(subdomain="brazosbend")
with core_tenancy.tenant_context(tenant.id):
    dana = identity_models.User.objects.filter(tenant_id=tenant.id, email__startswith="dana").first()
    order = work_tables.WorkOrder.objects.get(order_no="WO-0027")
    if order.assignee_technician_id is None and order.assignee_crew_id is None:
        print("WO-0027 already unassigned — left alone")
    else:
        dispatch.record_act(dana, order.id, {"act": "unassign"})
        print("WO-0027 taken off its holder by", dana.full_name, "(unassign act, audited)")
