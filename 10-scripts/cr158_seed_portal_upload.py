#!/usr/bin/env python3
"""cr158_seed_portal_upload — the world for the portal document-upload walk.

Spec `07-frontend/e2e/CR-158-portal-application-documents.spec.ts` (`CR-158-BRC10`).

PO 2026-10-01, verbatim: *"When you take utilty take it for 6 utility services water,
trash, sewer, fire, solar and battery - self service portal"*. So this REUSES the
J75 signup — `Six Rivers Utility` (`sixrivers`), exactly those six services and
nothing else, through the real signup service — and adds the two things a portal
walk needs and J75 does not:

  * the portal switched LIVE (requests on), through `portal.settings_service`;
  * one empty address, `88 Riverbend Way`, whose one unit carries service points
    for all six — so the applicant's availability check MATCHES and the request
    asks for water and solar (and the other four) as a NEW CONNECTION.

Idempotent: re-running changes nothing that is already there.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        python ../10-scripts/cr158_seed_portal_upload.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

ADDRESS = "88 Riverbend Way"
SERVICES = ["water", "sewer", "trash", "fire", "battery", "solar"]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    six = _load("seed_six_service_one_time", REPO / "10-scripts/seed_six_service_one_time.py")
    six.sjf.django_setup()
    six.provision()

    from django.db import transaction

    from apps.portal import settings_service
    from apps.tenancy import models as tm
    from core import tenancy as core_tenancy
    from tests.journey_cohort_fixtures import _premises_for, _unit_on

    tenant, actor = six.sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        with transaction.atomic():
            enabled = sorted(
                tm.TenantService.objects.filter(tenant=tenant, enabled=True).values_list(
                    "service__code", flat=True
                )
            )
            premises_id = _premises_for(tenant, actor, ADDRESS, SERVICES)
            _unit_on(tenant, actor, premises_id, "Main", SERVICES)
            settings_service.save_settings(actor, tenant.id, {"is_live": True})
    print("CR-158 portal upload world (Six Rivers Utility):")
    print(f"  services on ......... {', '.join(enabled)}")
    print(f"  address ............. {ADDRESS} (one unit, six service points)")
    print("  portal .............. live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
