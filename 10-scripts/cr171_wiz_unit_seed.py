"""CR-171-BRC10 lane MVI-WIZ-UNIT — give one vacant sample unit the shapes
image 30/31 draw, on a lane database, so step 1 can be photographed.

Run AFTER `seed_demo` and `load_sample_data --tenant brazosbend`:

    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
      python manage.py shell < ../10-scripts/cr171_wiz_unit_seed.py

Through the real services (never a row write): the unit's water meter gains
its facts (serial, make and model, seal, certified to — image 31's line) and a
behind-the-meter backflow preventer is fitted under it with a test date (image
30's *Not read · test due …*). Every figure is an illustration (B14 rule 37).
Idempotent: a second run changes nothing it already set.
"""

from types import SimpleNamespace

from core import tenancy as core_tenancy

from apps.assets import models as am
from apps.assets import services as asset_services
from apps.identity.models import User
from apps.metering import models as mm
from apps.tenancy.models import Tenant

UNIT_NO = "SCW-U-042"
tenant = Tenant.objects.get(subdomain="brazosbend")
core_tenancy.set_current_tenant(tenant.id)
user = User.objects.get(email="dana@brazosbendutilities.com")
actor = SimpleNamespace(id=user.id, role="system_admin", user=user, tenant_id=tenant.id)
unit = mm.Unit.objects.get(tenant_id=tenant.id, unit_no=UNIT_NO)
on_unit = am.Asset.objects.filter(
    tenant_id=tenant.id, assetassignment__unit_id=unit.id, assetassignment__to_date__isnull=True
)
water = on_unit.filter(type__category="meters", unit__iexact="kgal").first() or on_unit.filter(
    type__category="meters"
).first()
asset_services.update_asset(
    actor,
    water.id,
    {
        "serial_no": "77123",
        "manufacturer": "Badger",
        "model": "M25",
        "seal_no": "S-0912",
        "certification_due": "2027-03-03",
    },
)
if not on_unit.filter(type__category="behind_the_meter").exists():
    asset_services.create_asset(
        actor,
        {
            "type": "backflow",
            "asset_no": f"BF-{UNIT_NO[-3:]}",
            "service": "water",
            "parent_asset_no": water.asset_no,
            "unit_id": str(unit.id),
            "install_date": "2025-03-15",
            "status": "active",
            "last_test_date": "2026-03-15",
            "test_interval_months": 12,
        },
    )
print(f"{UNIT_NO}: {water.asset_no} has its facts; device under it present")
