"""CR-168-BRC10 round 8, lane FIX-8B — the three jobs the walk photographs.

    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python ../10-scripts/cr168_r8_fix8b_walk_prep.py

1. FINISHED — a job on an account, raised from *Meter exchange — residential*,
   closed in the field with outcome *Passed* and NOT yet accepted: the order
   page's completed shape (images 04/06: *Send back…*, *Complete*, *Holder ·
   C-nnnnn*). Recorded through metering's guard-free private half, the same
   one `sample_data` uses for the demo's past — this is walk DATA, not a door.
2. NO PRIORITY — a dispatcher job raised under a name no catalogue type
   carries, so it has no priority and no `due_at` of its own (`DEF-WRK-9677`).
3. MOVE-OUT VISIT ROW — a real move-out through `customers.services.move_out`
   with ONE typed row (*Re-read*), exactly what the wizard's *+ Add work order*
   row posts (`DEF-WRK-9694`): the job must carry the *Final read* template.

Prints one JSON line per job.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.customers import models as customers_models  # noqa: E402
from apps.customers import services as customers_services  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import connections as w6  # noqa: E402
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.work import models as work_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def main() -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    with core_tenancy.tenant_context(tenant.id):
        office = identity_models.User.objects.get(tenant_id=tenant.id, email="dana@brazosbendutilities.com")
        dana = SimpleNamespace(id=office.id, pk=office.id, role="system_admin", tenant_id=tenant.id,
                               full_name=office.full_name, email=office.email, is_authenticated=True)
        # Accounts a CUSTOMER holds (`customer_accounts`), so the Holder line
        # has a customer number to show (`DEF-WRK-9678`).
        held = customers_models.CustomerAccount.objects.filter(tenant_id=tenant.id).values_list("account_id", flat=True)
        accounts = list(customers_models.Account.objects.filter(tenant_id=tenant.id, unit_id__isnull=False, id__in=held)
                        .exclude(status__behavior_class="terminal").order_by("account_no")[:2])
        first, second = accounts[0], accounts[1]
        unit = first.unit
        template = work_tables.WorkOrderTemplate.objects.filter(
            tenant_id=tenant.id, name="Meter exchange — residential", active=True
        ).first()

        # 1 · finished, awaiting acceptance
        # No template: its safety lines would each need a field tick first
        # (`work.order.finish_safety_first`), which is the phone's act.
        done = w6.create_work_order(dana, None, {
            "type": template.name if template else "Meter exchange — residential",
            "service": template.service.code if template else "water",
            "premises_id": str(unit.premises_id), "unit_id": str(unit.id),
            "account_id": str(first.id), "source": "dispatcher",
        })
        row = work_tables.WorkOrder.objects.get(pk=done["id"])
        w6._record_field_result(dana, row, field_data={"walk": "FIX-8B"}, outcome=work_tables.OUTCOME_PASSED)
        print(json.dumps({"job": "finished", "order_no": done["order_no"], "account": first.account_no}))

        # 2 · no priority
        bare = w6.create_work_order(dana, None, {
            "type": "Check a noisy meter box (walk)", "service": "water",
            "premises_id": str(unit.premises_id), "account_id": str(first.id), "source": "dispatcher",
        })
        bare_row = work_tables.WorkOrder.objects.get(pk=bare["id"])
        print(json.dumps({"job": "no_priority", "order_no": bare["order_no"],
                          "priority": bare_row.priority_id, "due_at": bare_row.due_at}, default=str))

        # 3 · move-out with one typed visit row
        re_read = work_models.WorkOrderType.objects.get(tenant_id=tenant.id, code="RE_READ")
        result = customers_services.move_out(dana, str(second.id), {
            "moved_out_on": timezone.localdate().isoformat(),
            "field_visit": {"orders": [{"type_id": str(re_read.id)}]},
        })
        raised = result["work_orders"][0]
        made = work_tables.WorkOrder.objects.get(pk=raised["id"])
        print(json.dumps({"job": "move_out_row", "order_no": raised["order_no"], "move_no": result.get("move_no"),
                          "account": second.account_no,
                          "template": made.template.name if made.template_id else None,
                          "template_version": made.template_version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
