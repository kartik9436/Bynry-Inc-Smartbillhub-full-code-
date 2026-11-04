"""CR-168-BRC10 round 6, lane SRV-5 — the walk's server-side steps.

Run through the Django shell against the walk's PostgreSQL database:

    SRV5_ACT=prep  python manage.py shell < ../10-scripts/cr168_srv5_walk_setup.py
    SRV5_ACT=field SRV5_ORDER=<order no> python manage.py shell < …   # Patel takes it, sets off, closes Passed
    SRV5_ACT=decline SRV5_ORDER=<order no> python manage.py shell < … # Chen declines it

`prep` makes the walk's customer ELECT email and text (`accounts.paperless`,
`.sms_reminders` — the customer's own choice, which the visit messages honour)
and sets the utility's at-risk window to 4 h. It prints one JSON line the
browser walk reads. The field steps stand in for the phone, which lane FIELD-2
already walked (`cr168_field2_walk.mjs`); here the subject is what the office
and the customer are TOLD.
"""

import json
import os
from types import SimpleNamespace

from apps.customers.models import Account
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering.models import Unit
from apps.tenancy.models import Tenant
from apps.work import mobile, workforce
from apps.work import models as wm
from core import tenancy as core_tenancy

ACT = os.environ.get("SRV5_ACT", "prep")
ACCOUNT = os.environ.get("SRV5_ACCOUNT", "AC-2026-00050")
tenant = Tenant.objects.get(subdomain="brazosbend")


def _tech(slug):
    for row in wm.Technician.objects.select_related("user"):
        if workforce.technician_slug(row) == slug:
            return row
    raise SystemExit(f"no technician {slug}")


def _phone(row):
    return SimpleNamespace(id=row.user_id, role="field_technician")


with core_tenancy.tenant_context(tenant.id):
    if ACT == "prep":
        account = Account.objects.get(account_no=ACCOUNT)
        Account.objects.filter(pk=account.pk).update(paperless=True, sms_reminders=True)
        unit = Unit.objects.select_related("premises").get(pk=account.unit_id)
        wm.WorkSettings.objects.update_or_create(
            tenant_id=tenant.id, defaults={"at_risk_window_hours": 4}
        )
        services = list(unit.premises.services_available or [])
        print("SRV5 " + json.dumps({
            "account_no": account.account_no,
            "unit_id": str(unit.id),
            "premises_id": str(unit.premises_id),
            "address": unit.premises.address_line,
            "service": "water" if "water" in services else (services[0] if services else "electric"),
            "patel": str(_tech("r-patel").id),
            "chen": str(_tech("m-chen").id),
        }))
    elif ACT == "field":
        order = work_tables.WorkOrder.objects.get(order_no=os.environ["SRV5_ORDER"])
        patel = _phone(_tech("r-patel"))
        mobile.accept_job(patel, order.id)
        mobile.field_act(patel, order.id, {"act": "depart"})
        mobile.field_act(patel, order.id, {"act": "arrive"})
        w6.submit_field_result(patel, order.id, field_data={"walk": True}, outcome="passed")
        print("SRV5 field done", order.order_no)
    elif ACT == "decline":
        order = work_tables.WorkOrder.objects.get(order_no=os.environ["SRV5_ORDER"])
        mobile.decline_job(_phone(_tech("m-chen")), order.id, {"reason": "Van in the shop"})
        print("SRV5 declined", order.order_no)
