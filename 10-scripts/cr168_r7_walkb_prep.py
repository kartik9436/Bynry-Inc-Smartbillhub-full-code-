#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 round 7, lane WALK-B — the jobs the technician-app
#          rulings are proved on once more (shared tablet, 300 m fix, replay,
#          2 MB photo, accept held while photos upload, reassigned while
#          offline, two same-day readings). Raised through the product's own
#          services as Dana, exactly as `technician_api_setup.py` does — never a
#          row inserted to look like one.
# ───────────────────────────────────────────────────────
"""Raise one dispatcher job per proof, on a single-meter unit's electric meter,
from the per-meter template *Final read — residential* (one photo-required
task, one reading that posts as a meter read, one safety line), assigned and
scheduled to R. Patel (the shared-tablet pair: one to Patel, one to M. Chen).

    cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python ../10-scripts/cr168_r7_walkb_prep.py --tech-password '…'

Prints `<proof> <order_no> <order_id> <meter> <technician>` per job, as JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import technician_api_setup as setup  # noqa: E402  (django.setup() runs on import)

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import connections as w6  # noqa: E402
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.work import models as work_models  # noqa: E402
from apps.work.seams import assets_seam, metering_seam  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: proof -> (meter asset_no, technician email)
PROOFS = {
    "same_day": ("E-5000", "r.patel@sample.test"),
    "fix_300m": ("E-5005", "r.patel@sample.test"),
    "replay": ("E-5006", "r.patel@sample.test"),
    "photo_2mb_accept_hold": ("E-5007", "r.patel@sample.test"),
    "reassigned_offline": ("E-5008", "r.patel@sample.test"),
    "shared_x": ("E-5009", "r.patel@sample.test"),
    "shared_y": ("E-5010", "m.chen@sample.test"),
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tenant", default="brazosbend")
    p.add_argument("--tech-password", required=True)
    a = p.parse_args()
    tenant = tenancy_models.Tenant.objects.get(subdomain=a.tenant)
    out = []
    with core_tenancy.tenant_context(tenant.id):
        from types import SimpleNamespace
        from django.contrib.auth.hashers import make_password

        office = identity_models.User.objects.get(tenant_id=tenant.id, email="dana@brazosbendutilities.com")
        dana = SimpleNamespace(id=office.id, pk=office.id, role="system_admin", tenant_id=tenant.id,
                               full_name=office.full_name, email=office.email, is_authenticated=True)
        techs = {}
        for email in ("r.patel@sample.test", "m.chen@sample.test"):
            user = identity_models.User.objects.get(tenant_id=tenant.id, email=email)
            user.password_hash = make_password(a.tech_password)
            user.must_change_password = False
            user.save(update_fields=["password_hash", "must_change_password"])
            techs[email] = work_models.Technician.objects.get(tenant_id=tenant.id, user_id=user.id)
        tid = setup._template(dana)
        from apps.assets import models as assets_models

        for proof, (asset_no, email) in PROOFS.items():
            asset = assets_models.Asset.objects.get(tenant_id=tenant.id, asset_no=asset_no)
            walk = w6._asset_walk(tenant.id, asset.id)
            row = w6.create_work_order(dana, None, {
                "premises_id": str(walk["premises_id"]), "asset_id": str(asset.id),
                "type": setup.TEMPLATE, "template_id": tid, "source": "dispatcher",
            })
            setup._give(dana, row["id"], techs[email])
            order = work_tables.WorkOrder.objects.get(pk=row["id"])
            out.append({"proof": proof, "order_no": order.order_no, "order_id": str(order.id),
                        "meter": asset_no, "technician": email})
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
