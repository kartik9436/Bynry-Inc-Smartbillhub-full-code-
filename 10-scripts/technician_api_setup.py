#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 §F, lane FIELD-FIX — the jobs `technician_api_walk.py`
#          completes: one per source the PO asked about (move-in, move-out,
#          transfer, reconnect, New Connect, a dispatcher's job), each given to
#          R. Patel, plus a job for M. Chen (the shared-tablet case).
# Rules:   every write is the product's own service, as Dana (the office) —
#          never a row inserted to look like one.
# ───────────────────────────────────────────────────────
"""Raise the walk's jobs on a seeded tenant, through the product's services.

    cd 06-backend && DATABASE_URL=postgres://…/sbh_x DJANGO_SETTINGS_MODULE=config.settings.local \
      python ../10-scripts/technician_api_setup.py --tenant brazosbend --tech-password '…'

* A per-meter template *Final read — residential* (electric): two tasks, the
  first asking for a photograph, one reading that posts as a meter read, and
  one safety line — published through `templates_svc`, as Settings does.
* move-out: `customers.services.move_out` with the visit ticked (the real
  door, which ends the agreements first — the `DEF-WRK-9620` case).
* move-in, transfer, reconnect: `work.from_flows.raise_for`, the ONE raise
  service those doors call, on an account that has a unit with one meter.
* New Connect: `metering.connections.create_work_order` on a build, stamped
  `new_connect` — the call the New Connect commit makes for each job — from
  the tenant's first connection-sequence template that posts no meter read.
* dispatcher: `create_work_order` on a premises, as *New work order* does.
* Every job is assigned and scheduled to R. Patel through `dispatch.record_act`;
  one extra job goes to M. Chen. R. Patel's and M. Chen's passwords are set
  (the seed discards them on purpose).

Prints one line per job: `<order_no> <source> <technician>`.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.contrib.auth.hashers import make_password  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.customers import models as customers_models  # noqa: E402
from apps.customers import services as customers_services  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import connections as w6  # noqa: E402
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.work import dispatch, from_flows, templates_svc  # noqa: E402
from apps.work import models as work_models  # noqa: E402
from apps.work.seams import assets_seam, metering_seam  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TEMPLATE = "Final read — residential"


def _template(actor) -> str:
    found = work_tables.WorkOrderTemplate.objects.filter(name=TEMPLATE, active=True).first()
    if found is not None and (found.version or 0) >= 1:
        return str(found.id)
    header = templates_svc.create_draft(
        actor, {"name": TEMPLATE, "service": "electric", "scope": "per_asset", "sequence": 0}
    )
    tid = header["id"]
    templates_svc.replace_collection(actor, tid, "tasks", [
        {"title": "Photograph the meter face", "est_minutes": 3, "photo_required": True},
        {"title": "Seal and tidy", "est_minutes": 2},
    ])
    templates_svc.replace_collection(actor, tid, "readings", [
        {"prompt": "Final read", "unit_of_measure": "kWh", "min": 0, "max": 999999,
         "required": True, "posts_as_meter_read": True},
    ])
    templates_svc.replace_collection(actor, tid, "safety", [
        {"text": "Gloves and eye protection on", "is_mandatory": True},
    ])
    templates_svc.publish(actor, tid)
    return tid


def _accounts_with_one_meter(limit: int) -> list:
    """Active accounts on a unit whose electric point carries exactly one
    in-service meter — the single-meter case `DEF-WRK-9620` fixes."""
    found = []
    for account in customers_models.Account.objects.exclude(
        status__behavior_class="terminal"
    ).exclude(unit_id=None).order_by("account_no"):
        points = metering_seam.service_point_ids_on_unit(account.unit_id, "electric")
        if len(assets_seam.in_service_meters_on_points(points)) == 1:
            found.append(account)
        if len(found) >= limit:
            break
    return found


def _give(actor, order_id, technician) -> None:
    when = (timezone.now() + timedelta(hours=2)).replace(microsecond=0).isoformat()
    dispatch.record_act(actor, order_id, {"act": "assign", "technician_id": str(technician.id)}, push=False)
    dispatch.record_act(
        actor, order_id,
        {"act": "schedule", "technician_id": str(technician.id), "scheduled_for": when},
        push=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--office-email", default="dana@brazosbendutilities.com")
    parser.add_argument("--tech-password", required=True)
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.get(subdomain=args.tenant)
    with core_tenancy.tenant_context(tenant.id):
        from types import SimpleNamespace

        office = identity_models.User.objects.get(tenant_id=tenant.id, email=args.office_email)
        membership = identity_models.TenantMembership.objects.filter(
            tenant_id=tenant.id, user_id=office.id
        ).select_related("role").first()
        role = getattr(getattr(membership, "role", None), "code", None) or "system_admin"
        # The office's actor in the shape every service reads (id, role).
        dana = SimpleNamespace(id=office.id, pk=office.id, role=role, tenant_id=tenant.id,
                               full_name=office.full_name, email=office.email, is_authenticated=True)
        techs = {}
        for email in ("r.patel@sample.test", "m.chen@sample.test"):
            user = identity_models.User.objects.get(tenant_id=tenant.id, email=email)
            user.password_hash = make_password(args.tech_password)
            user.must_change_password = False
            user.save(update_fields=["password_hash", "must_change_password"])
            techs[email] = work_models.Technician.objects.get(tenant_id=tenant.id, user_id=user.id)
        patel, chen = techs["r.patel@sample.test"], techs["m.chen@sample.test"]
        tid = _template(dana)
        accounts = _accounts_with_one_meter(5)
        if len(accounts) < 5:
            print(f"only {len(accounts)} single-meter accounts found; need 5", file=sys.stderr)
            return 1
        made: list[tuple[str, str, str]] = []

        def note(order_id, source, tech):
            row = work_tables.WorkOrder.objects.get(pk=order_id)
            made.append((row.order_no, source, tech.user.email))

        # move-out — the real door.
        out = customers_services.move_out(
            dana, accounts[0].id,
            {"moved_out_on": timezone.localdate().isoformat(), "field_visit": {"template_ids": [tid]}},
        )
        for row in out.get("work_orders") or []:
            _give(dana, row["id"], patel)
            note(row["id"], "move_out", patel)
        # move-in, transfer, reconnect — the one raise service their doors call.
        for flow, account in (
            (from_flows.FLOW_MOVE_IN, accounts[1]),
            (from_flows.FLOW_TRANSFER, accounts[2]),
            (from_flows.FLOW_RECONNECT, accounts[3]),
        ):
            raised = from_flows.raise_for(flow, account.id, [tid], dana)
            for row in raised["raised"]:
                _give(dana, row["id"], patel)
                note(row["id"], flow, patel)
        # New Connect — a build's job, stamped as the commit stamps it.
        connection = work_tables.Connection.objects.exclude(premises_id=None).order_by("connection_no").first()
        # A connection-sequence template that posts no meter read — a build
        # has no meter until its meter is set, so a reading could post nowhere.
        nc_template = next(
            t for t in work_tables.WorkOrderTemplate.objects.filter(active=True, sequence__gt=0).order_by("template_no")
            if not work_models.WorkOrderTemplateReading.objects.filter(
                template_id=t.id, posts_as_meter_read=True
            ).exists()
        )
        nc = w6.create_work_order(dana, connection.id, {
            "type": nc_template.name, "template_id": str(nc_template.id), "source": "new_connect",
            "source_ref": connection.connection_no,
        })
        _give(dana, nc["id"], patel)
        note(nc["id"], "new_connect", patel)
        # A dispatcher's job on a unit's meter.
        meter_points = metering_seam.service_point_ids_on_unit(accounts[4].unit_id, "electric")
        meter = assets_seam.in_service_meters_on_points(meter_points)[0]
        premises_id = metering_seam.premises_id_of_unit(accounts[4].unit_id)
        dj = w6.create_work_order(dana, None, {
            "premises_id": str(premises_id), "asset_id": meter["id"], "type": TEMPLATE,
            "template_id": tid, "source": "dispatcher",
        })
        _give(dana, dj["id"], patel)
        note(dj["id"], "dispatcher", patel)
        # M. Chen's own job — the shared tablet's second login.
        mc = w6.create_work_order(dana, None, {
            "premises_id": str(premises_id), "asset_id": meter["id"], "type": TEMPLATE,
            "template_id": tid, "source": "dispatcher",
        })
        _give(dana, mc["id"], chen)
        note(mc["id"], "dispatcher", chen)
    for order_no, source, email in made:
        print(order_no, source, email)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
