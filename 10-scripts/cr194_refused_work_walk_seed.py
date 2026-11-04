"""CR-194-BRC10 walkthrough seed — the PO's worked example, made real.

D. Ortiz accepts a meter-read job, goes offline, the dispatcher gives the job
to M. Chen, and Ortiz's phone later sends three readings and a photograph:
all four are refused back to the phone AND kept for the office. One route
reading with no unit is refused by the reads door and kept too.

Run against a DEVELOPMENT database seeded with `seed_demo` (never prod)::

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://…/cr194 JOBS_EAGER=false \\
      python ../10-scripts/cr194_refused_work_walk_seed.py

Then `10-scripts/cr194_refused_work_walkthrough.mjs` photographs the office.
Every write goes through the owning service (`dispatch`, `mobile`, `sync`,
`field_reads`); the reading rows are the one direct create, as the tests do.
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import connections as w6  # noqa: E402
from apps.metering import field_reads  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.work import dispatch, mobile, sync  # noqa: E402
from apps.work import models as work_models  # noqa: E402
from apps.work import services as work_services  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TENANT = os.environ.get("TENANT", "brazosbend")


def main() -> None:
    tenant = tenancy_models.Tenant.objects.get(subdomain=TENANT)
    with core_tenancy.tenant_context(tenant.id):
        for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
            work_services.seed_reference_list(code, [], "walk")
        owner = identity_models.User.objects.filter(tenant_id=tenant.id).filter(email="dana@brazosbendutilities.com").first()
        office = SimpleNamespace(id=owner.id, role="utility_admin")

        def person(email: str, name: str) -> work_models.Technician:
            user, _ = identity_models.User.objects.get_or_create(
                tenant_id=tenant.id, email=email, defaults={"full_name": name}
            )
            tech, _ = work_models.Technician.objects.get_or_create(tenant_id=tenant.id, user=user)
            return tech

        ortiz = person("d.ortiz@walk.test", "D. Ortiz")
        chen = person("m.chen@walk.test", "M. Chen")
        premises = metering_models.Premises.objects.filter(tenant_id=tenant.id).first()
        oid = w6.create_work_order(
            office, None, {"type": "Meter read", "service": "electric", "premises_id": str(premises.id)}
        )["id"]
        dispatch.record_act(office, oid, {"act": "assign", "technician_id": str(ortiz.id)}, push=False)
        rows = [
            work_models.WorkOrderReading.objects.create(
                tenant_id=tenant.id, work_order_id=oid, seq=10_000 + n, prompt=prompt,
                unit_of_measure="kWh", required=False,
            )
            for n, prompt in enumerate(("Main meter", "Sub-meter A", "Sub-meter B"), start=1)
        ]
        as_ortiz = SimpleNamespace(id=ortiz.user_id, role="field_technician")
        mobile.accept_job(as_ortiz, oid)
        token = mobile.issue_capture_token(as_ortiz)["capture_token"]
        dispatch.record_act(
            office, oid, {"act": "assign", "technician_id": str(chen.id), "reason": "Ortiz is off sick"}, push=False
        )
        items = [
            {
                "key": f"walk-{uuid.uuid4()}", "kind": "reading", "seq": n, "capture_token": token,
                "captured_at": f"2026-10-26T14:0{n}:00Z",
                "location": {"lat": "29.5601", "lng": "-95.8072", "accuracy_m": "8.0", "fix_at": "2026-10-26T14:00:00Z"},
                "payload": {"reading_id": str(row.id), "value": str(40_000 + n), "unit": "kWh"},
            }
            for n, row in enumerate(rows, start=1)
        ]
        items.append({
            "key": f"walk-{uuid.uuid4()}", "kind": "photo", "seq": 9, "capture_token": token,
            "captured_at": "2026-10-26T14:05:00Z",
            "payload": {"photo_id": str(uuid.uuid4()), "sha256": hashlib.sha256(b"x").hexdigest(),
                        "reading_id": str(rows[0].id)},
        })
        out = sync.sync_batch(as_ortiz, oid, {"items": items})
        print("job door:", [(i["result"], i["detail"].get("reason"), i["detail"].get("kept_for_office")) for i in out["items"]])
        reads = field_reads.sync_reads(
            as_ortiz,
            {"items": [{"key": f"walk-r-{uuid.uuid4()}", "kind": "teleport", "captured_at": "2026-10-26T15:00:00Z"}]},
        )
        print("reads door:", [(i["result"], i.get("reason"), (i.get("detail") or {}).get("kept_for_office")) for i in reads["items"]])
        from apps.work import connection_models
        print("order:", connection_models.WorkOrder.objects.get(pk=oid).order_no)


if __name__ == "__main__":
    main()
