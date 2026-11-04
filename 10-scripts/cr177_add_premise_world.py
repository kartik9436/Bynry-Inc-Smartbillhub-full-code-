"""cr177_add_premise_world — the Add a premise walk's world, on a LOCAL PostgreSQL.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false python ../10-scripts/cr177_add_premise_world.py setup|connect|disconnect|readback

Run after `manage.py migrate` + `manage.py seed_demo` (Brazos Bend = the walk's utility).

``setup`` (idempotent) — what the 14 drawing states need, and nothing else:
  * premise fields *Roof age* (number, REQUIRED), *Roof material* (text) and
    *EV charged on site* (select), placed Input on Add a premise (`S16`);
  * an existing premise at **101 Silver Creek Rd, Silver Creek, TX 78611**
    (for *This address already exists.*);
  * a master account **Bramble Property Group**, a company, owning **1 Bramble
    Way** whose *Managed by* is **Northside Management** (for the Owner card).

``clean`` removes the premises a previous walk created (LOCAL database only).

``connect`` / ``disconnect`` — the City map connection for this utility, on a
RECORDED `.example` host (`apps/integrations/gis_fixtures.FAST_HOST`): no real
City is ever dialled. ``readback`` prints the last premise created, as the
database holds it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django

django.setup()


def _sjf():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _ctx():
    from core import tenancy as core_tenancy

    tenant, actor = _sjf().tenant_and_actor()
    return tenant, actor, core_tenancy.tenant_context(tenant.id)


def setup() -> None:

    from apps.metering import models as mm
    from apps.metering import services as ms
    from apps.tenancy import models as tm
    from apps.tenancy import services as ts

    tenant, actor, ctx = _ctx()
    with ctx:
        wanted = [
            ({"label": "Roof age", "entity": "premises", "data_type": "number", "is_required": True}, "roof"),
            ({"label": "Roof material", "entity": "premises", "data_type": "text"}, "material"),
            (
                {"label": "EV charged on site", "entity": "premises", "data_type": "select", "options": ["Yes", "No"]},
                "ev",
            ),
        ]
        have = {row.label for row in tm.CustomField.objects.filter(entity="premises")} if hasattr(tm, "CustomField") else set()
        for payload, _ in wanted:
            if payload["label"] in have:
                continue
            made = ts.create_custom_field(actor, payload)
            ts.save_custom_field_placement(actor, made["id"], {"S16": "input", "PREMISE_EDIT": "input", "PREMISE_PAGE": "view"})
            print("custom field:", payload["label"])
        if not mm.Premises.objects.filter(address_line="101 Silver Creek Rd").exists():
            made = ms.create_premises(
                actor,
                {"address_line": "101 Silver Creek Rd", "city": "Silver Creek", "state": "TX", "postal_code": "78611",
                 "units": [{"label": "1"}]},
            )
            print("existing premise:", made["premise_no"])
        if not mm.Premises.objects.filter(address_line="1 Bramble Way").exists():
            made = ms.create_premises(
                actor,
                {
                    "address_line": "1 Bramble Way", "city": "Silver Creek", "state": "TX", "postal_code": "78611",
                    "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                    "owner_manager": "Northside Management",
                    "owner_kind": "company", "owner_tax_id": "74-3182640", "owner_account_type": "commercial",
                },
            )
            print("Bramble premise:", made["premise_no"], "master account:", made.get("master_account_no"))
            row = mm.Premises.objects.get(pk=made["id"])
            if row.master_account_id:
                from apps.customers import models as cmm
                links = cmm.CustomerAccount.objects.filter(account_id=row.master_account_id).select_related("customer")
                for link in links:
                    link.customer.display_name = "Bramble Property Group"
                    link.customer.save(update_fields=["display_name"])
                print("named the holder Bramble Property Group")
    print("tenant:", tenant.subdomain)


def connect() -> None:
    from apps.integrations import gis, gis_fixtures
    from apps.integrations import models as im
    from apps.integrations import services as isv

    tenant, actor, ctx = _ctx()
    with ctx:
        row = isv.connection_for(tenant.id, gis.PROVIDER_KEY)
        if row is not None:  # a previous walk's row, switched off by ``disconnect``
            im.IntegrationConnection.objects.filter(pk=row.pk).update(enabled=True)
            print("City map re-enabled (recorded host):", gis.city_state(tenant.id))
            return
        isv.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=im.ENVIRONMENT_PRODUCTION,
            config={"base_url": f"https://{gis_fixtures.FAST_HOST}/addr"},
            cadence=im.CADENCE_NIGHTLY,
        )
        print("City map connected (recorded host):", gis.city_state(tenant.id))


def disconnect() -> None:
    from apps.integrations import gis
    from apps.integrations import models as im
    from apps.integrations import services as isv

    tenant, _actor, ctx = _ctx()
    with ctx:
        row = isv.connection_for(tenant.id, gis.PROVIDER_KEY)
        if row is not None:
            im.IntegrationConnection.objects.filter(pk=row.pk).update(enabled=False)
        print("City map:", gis.city_state(tenant.id))


#: The two premises the walk itself creates. ``clean`` removes them from the
#: LOCAL database so a second run meets the same screens as the first rather
#: than its own *This address already exists.*
WALK_STREETS = ("3721 S Village Dr", "3721 S Village Dr,", "1408 Pecan St")


def clean() -> None:
    from apps.metering import models as mm
    from django.db import transaction

    _tenant, _actor, ctx = _ctx()
    with ctx, transaction.atomic():
        rows = list(mm.Premises.objects.filter(address_line__in=WALK_STREETS))
        for row in rows:
            for unit in mm.Unit.objects.filter(premises=row):
                mm.ServicePoint.objects.filter(unit=unit).delete()
                unit.delete()
            row.delete()
        print("removed the walk's own premises:", [row.premise_no for row in rows])


def readback() -> None:
    from apps.metering import models as mm

    _tenant, _actor, ctx = _ctx()
    with ctx:
        row = mm.Premises.objects.order_by("-created_at").first()
        print(row.premise_no, "|", row.address_line, "|", row.city, row.state, row.postal_code, "|", row.services_available,
              "| parcel", row.gis_parcel_id, "| point", row.lat, row.lng, "| unchecked", row.gis_unchecked,
              "| checked_at", row.gis_checked_at, "| master", row.master_account_id, "| custom", row.custom_data,
              "| units", mm.Unit.objects.filter(premises=row).count())


if __name__ == "__main__":
    {"setup": setup, "clean": clean, "connect": connect, "disconnect": disconnect, "readback": readback}[sys.argv[1]]()
