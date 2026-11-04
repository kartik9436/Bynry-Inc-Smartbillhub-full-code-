#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — the REAL answers of the routes
#           SRV-2 added or changed, recorded on PostgreSQL for the screens'
#           tests (lane RAISE's request after DEF-WRK-9600/9601: two shipped
#           crashes from hand-typed fixtures)
# Rules:    hard-won law 7 (a fixture that cannot tell a real shape from a
#           guessed one hides the defect) · B14 rule 31 (ids are link targets)
# ───────────────────────────────────────────────────────
"""Record what the Work server ACTUALLY answers, into checked-in JSON.

    cd 06-backend && DATABASE_URL=postgres://…/<db> \\
        DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        python ../10-scripts/cr168_srv2_record_shapes.py

Runs against a database seeded with `seed_demo` + `load_sample_data --tenant
brazosbend` (the demo the 65 images were captured on). Calls each VIEW through
DRF's request factory as Dana Whitfield (System Admin) inside the tenant
context — the same code path a browser reaches, minus the session cookie — and
writes `07-frontend/src/features/work/__fixtures__/<name>.recorded.json`.

⚠ TWO OF THE RECORDINGS WRITE (the bulk raise raises jobs; send back reopens a
finished one). Run it on a lane database, never on one a person is using.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "06-backend"
OUT = ROOT / "07-frontend" / "src" / "features" / "work" / "__fixtures__"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from apps.identity import models as identity_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def call(view, method, path, *, user, tenant, data=None, **kwargs):
    factory = APIRequestFactory()
    make = getattr(factory, method)
    request = make(path, data, format="json") if method == "post" else make(path, data)
    force_authenticate(request, user=user)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        response = view(request, **kwargs)
    response.render() if hasattr(response, "render") else None
    if response.status_code != 200:
        raise SystemExit(f"{path}: {response.status_code} {getattr(response, 'data', '')}")
    return json.loads(json.dumps(response.data, default=str))


def write(name: str, body) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.recorded.json"
    path.write_text(json.dumps(body, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    from apps.work import connection_models as work_tables
    from apps.metering import models as metering_models
    from apps.work import api as work_api

    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    with core_tenancy.tenant_context(tenant.id):
        dana = identity_models.User.objects.filter(
            tenant_id=tenant.id, email__istartswith="dana"
        ).first()
        order = (
            work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, state="planned")
            .exclude(template_id=None)
            .order_by("order_no")
            .first()
        )
        template = work_tables.WorkOrderTemplate.objects.filter(
            tenant_id=tenant.id, active=True, version__gte=1
        ).order_by("name").first()
        premises = (
            metering_models.Premises.objects.filter(tenant_id=tenant.id, unit__isnull=False)
            .distinct()
            .order_by("address_line")
            .first()
        )
        units = list(
            metering_models.Unit.objects.filter(tenant_id=tenant.id, premises=premises)
            .order_by("label")
            .values_list("id", flat=True)[:3]
        )
        from apps.assets import models as assets_models

        asset = (
            assets_models.Asset.objects.filter(tenant_id=tenant.id, service_point__isnull=False)
            .order_by("asset_no")
            .first()
        )
        finished = (
            work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, state="completed", accepted_at=None)
            .order_by("order_no")
            .first()
        )
    base = f"/api/{tenant.subdomain}"
    unit_ids = ",".join(str(u) for u in units)

    write(
        "work-order-candidates",
        call(work_api.work_order_candidates, "get", f"{base}/work-orders/{order.id}/candidates",
             user=dana, tenant=tenant, order_id=order.id),
    )
    write(
        "work-raise-candidates",
        call(work_api.raise_candidates, "get", f"{base}/work/candidates",
             user=dana, tenant=tenant,
             data={"template_id": str(template.id), "premises_id": str(premises.id)}),
    )
    write(
        "work-raise-assets",
        call(work_api.raise_assets, "get", f"{base}/work/raise/assets",
             user=dana, tenant=tenant, data={"unit_ids": unit_ids}),
    )
    write(
        "asset-work-order-templates",
        call(work_api.asset_work_order_templates, "get",
             f"{base}/assets/{asset.id}/work-order-templates",
             user=dana, tenant=tenant, asset_id=asset.id),
    )
    write(
        "work-templates-for-the-raise",
        call(work_api.templates, "get", f"{base}/work/templates",
             user=dana, tenant=tenant, data={"f.raisable": "1"}),
    )
    write(
        "work-orders-bulk-raise",
        call(work_api.work_orders_bulk_raise, "post", f"{base}/work-orders/bulk-raise",
             user=dana, tenant=tenant,
             data={"type": "Leak investigation", "premises_id": str(premises.id),
                   "unit_ids": [str(u) for u in units],
                   "idempotency_key": f"recorded-{uuid.uuid4()}"}),
    )
    if finished is not None:
        write(
            "work-order-send-back",
            call(work_api.work_order_send_back, "post",
                 f"{base}/work-orders/{finished.id}/send-back",
                 user=dana, tenant=tenant, data={"reason": "The photograph is missing"},
                 order_id=finished.id),
        )


if __name__ == "__main__":
    main()
