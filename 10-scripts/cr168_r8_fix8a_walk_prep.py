"""CR-168-BRC10 round 8, lane FIX-8A — the PostgreSQL proof of DEF-WRK-9688.

Run from 06-backend with the lane database's settings:

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_wfix8a \
    DJANGO_SETTINGS_MODULE=config.settings.local \
    python ../10-scripts/cr168_r8_fix8a_walk_prep.py prepare --tech-password '…'
    … (the browser books 08:00–12:00 through `cr168_r8_fix8a_walk.mjs`) …
    python ../10-scripts/cr168_r8_fix8a_walk_prep.py report --order WO-00nn

`prepare` sets R. Patel's password and prints one open, unassigned order on a
Brazos Bend premises that has an account (so the customer text has somebody to
address). `report` prints what is STORED for that order (the instants, in UTC)
and what each surface reads back from it: the edit form's appointment, the
history label, the technician's day card, the customer's message context and
the printed sheet's line — the brief's three readers and two more.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.contrib.auth.hashers import make_password  # noqa: E402

from apps.identity.models import User  # noqa: E402
from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

TECH = "r.patel@sample.test"


def _tenant():
    return Tenant.objects.get(subdomain="brazosbend")


def prepare(args) -> None:
    tenant = _tenant()
    with tenant_context(tenant.id):
        user = User.objects.get(tenant_id=tenant.id, email=TECH)
        user.password_hash = make_password(args.tech_password)
        user.must_change_password = False
        user.save(update_fields=["password_hash", "must_change_password"])
        order = (
            work_tables.WorkOrder.objects.filter(
                tenant_id=tenant.id,
                state="planned",
                assignee_technician__isnull=True,
                assignee_crew__isnull=True,
                account__isnull=False,
            )
            .order_by("order_no")
            .first()
        )
        if order is None:
            order = (
                work_tables.WorkOrder.objects.filter(
                    tenant_id=tenant.id, state="planned", assignee_technician__isnull=True
                )
                .order_by("order_no")
                .first()
            )
        from apps.tenancy import selectors

        from apps.work import models as work_models

        tech = work_models.Technician.objects.get(tenant_id=tenant.id, user_id=user.id)
        print(f"ORDER {order.order_no} {order.id}")
        print(f"TECH {tech.id}")
        print(f"ZONE {selectors.tenant_timezone()}")


def report(args) -> None:
    from apps.work import edit, mobile, print_docs, visit_notices

    tenant = _tenant()
    with tenant_context(tenant.id):
        order = work_tables.WorkOrder.objects.get(tenant_id=tenant.id, order_no=args.order)
        print(f"stored window_start (UTC) {order.window_start.isoformat()}")
        print(f"stored window_end   (UTC) {order.window_end.isoformat()}")
        appt = edit._appointment(order)
        print(f"order/edit appointment    {appt['date']} {appt['start']}–{appt['end']} ({appt['time_zone']})")
        print(f"history label             {edit._window_label(order)}")
        card = mobile._job_card(order, None)
        print(f"technician day card       {card['appointment']['start']}–{card['appointment']['end']}")
        ctx = visit_notices.customer_context(order)
        print(f"customer text             {ctx['appointment_date']} · {ctx['appointment_window']}")
        row = {
            "window_start": order.window_start.isoformat(),
            "window_end": order.window_end.isoformat(),
            "due_at": None,
        }
        print(f"printed sheet             {print_docs.when_text(row)}")
        # The customer text is RENDERED from this context (`visit_notices.
        # tell_customer` → `render_context`); whether it is queued depends on the
        # account's chosen channels, which is not this defect.


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--tech-password", required=True)
    r = sub.add_parser("report")
    r.add_argument("--order", required=True)
    args = parser.parse_args()
    {"prepare": prepare, "report": report}[args.cmd](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
